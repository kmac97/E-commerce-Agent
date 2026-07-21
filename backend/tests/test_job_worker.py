# Regression check for Phase 1.5 (backend/database/client.py's job-queue
# helpers + backend/agents/job_worker.py's dispatch/orphan-reclaim logic).
# Uses an in-memory fake Supabase client (now with order()/limit() support,
# since claim_next_job and reclaim_orphaned_jobs both use them).
# Run with: python backend/tests/test_job_worker.py

import asyncio
import pathlib
import sys
from datetime import datetime, timedelta, timezone

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQueryBuilder:
    def __init__(self, store, table_name):
        self.store = store
        self.table_name = table_name
        self._op = None
        self._data = None
        self._filters = {}
        self._order_col = None
        self._limit = None

    def insert(self, data):
        self._op = "insert"
        self._data = data
        return self

    def update(self, data):
        self._op = "update"
        self._data = data
        return self

    def select(self, *_a):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, col, **_kw):
        self._order_col = col
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self.store[self.table_name]
        if self._op == "insert":
            row = dict(self._data)
            row.setdefault("id", f"{self.table_name}-{len(rows) + 1}")
            row.setdefault("created_at", f"{len(rows):05d}")  # deterministic ordering in tests
            if self.table_name == "jobs":
                row.setdefault("status", "pending")
                row.setdefault("attempts", 0)
            rows.append(row)
            return _FakeResult([row])
        if self._op == "select":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            if self._order_col:
                matched = sorted(matched, key=lambda r: r.get(self._order_col) or "")
            if self._limit is not None:
                matched = matched[: self._limit]
            return _FakeResult(matched)
        if self._op == "update":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            for r in matched:
                r.update(self._data)
            return _FakeResult(matched)
        return _FakeResult([])


class _FakeSupabase:
    def __init__(self):
        self.store = {"jobs": []}

    def table(self, name):
        self.store.setdefault(name, [])
        return _FakeQueryBuilder(self.store, name)


import database.client as db_client  # noqa: E402
db_client.supabase = _FakeSupabase()

import agents.job_worker as job_worker  # noqa: E402


async def _run():
    # ── enqueue / claim / complete ──
    job = await db_client.enqueue_job("research_task", {"task_id": "t1", "topic": "widgets"})
    assert job["status"] == "pending"
    assert job["attempts"] == 0

    claimed = await db_client.claim_next_job()
    assert claimed["id"] == job["id"]
    assert claimed["status"] == "running"
    assert claimed["locked_at"]

    # Attempts incremented in the underlying row.
    row = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job["id"])
    assert row["attempts"] == 1

    # Nothing else pending.
    assert await db_client.claim_next_job() is None

    await db_client.mark_job_complete(job["id"])
    row = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job["id"])
    assert row["status"] == "complete"

    # ── mark_job_failed ──
    job2 = await db_client.enqueue_job("research_task", {"task_id": "t2", "topic": "gadgets"})
    await db_client.claim_next_job()
    await db_client.mark_job_failed(job2["id"], "boom")
    row2 = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job2["id"])
    assert row2["status"] == "failed"
    assert row2["error"] == "boom"

    # ── reclaim_orphaned_jobs: stale running job gets reclaimed, recent one doesn't ──
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    fresh_time = datetime.now(timezone.utc).isoformat()
    db_client.supabase.store["jobs"].append({
        "id": "jobs-stale", "type": "research_task", "payload": {}, "status": "running",
        "locked_at": stale_time, "attempts": 1,
    })
    db_client.supabase.store["jobs"].append({
        "id": "jobs-fresh", "type": "research_task", "payload": {}, "status": "running",
        "locked_at": fresh_time, "attempts": 1,
    })
    reclaimed = await db_client.reclaim_orphaned_jobs(timeout_minutes=30)
    assert reclaimed == 1
    stale_row = next(r for r in db_client.supabase.store["jobs"] if r["id"] == "jobs-stale")
    fresh_row = next(r for r in db_client.supabase.store["jobs"] if r["id"] == "jobs-fresh")
    assert stale_row["status"] == "failed"
    assert "orphaned" in stale_row["error"]
    assert fresh_row["status"] == "running", "a recently-locked job must not be reclaimed"

    # ── job_worker dispatch ──
    calls = []

    async def fake_handler(task_id, topic, research_type):
        calls.append((task_id, topic, research_type))

    job_worker.register_job_handler("research_task", fake_handler)

    job3 = await db_client.enqueue_job(
        "research_task", {"task_id": "t3", "topic": "gizmos", "research_type": "product"}
    )
    claimed3 = await db_client.claim_next_job()
    await job_worker._run_one(claimed3)
    assert calls == [("t3", "gizmos", "product")]
    row3 = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job3["id"])
    assert row3["status"] == "complete"

    # A handler that raises -> job marked failed, not left stuck.
    async def failing_handler(**_kw):
        raise RuntimeError("agent blew up")

    job_worker.register_job_handler("research_task", failing_handler)
    job4 = await db_client.enqueue_job("research_task", {"task_id": "t4", "topic": "x", "research_type": "product"})
    claimed4 = await db_client.claim_next_job()
    await job_worker._run_one(claimed4)
    row4 = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job4["id"])
    assert row4["status"] == "failed"
    assert "agent blew up" in row4["error"]

    # Unregistered job type -> fails cleanly instead of crashing the loop.
    job5 = await db_client.enqueue_job("unknown_type", {})
    claimed5 = await db_client.claim_next_job()
    await job_worker._run_one(claimed5)
    row5 = next(r for r in db_client.supabase.store["jobs"] if r["id"] == job5["id"])
    assert row5["status"] == "failed"
    assert "No handler registered" in row5["error"]


if __name__ == "__main__":
    asyncio.run(_run())
    print("job worker checks passed")

# Regression check for the Phase 1.1 approval-gate DB helpers
# (backend/database/client.py's actions/approvals/audit_log functions).
#
# Uses a lightweight fake Supabase client (records calls, applies filters/
# updates in-memory) rather than a real Supabase connection -- these
# functions are pure query-building + call-sequencing logic, which is
# exactly what this fake can verify without needing production credentials.
# Run with: python backend/tests/test_action_approval_client.py

import asyncio
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, store, table_name):
        self.store = store
        self.table_name = table_name
        self._op = None
        self._data = None
        self._filters = {}

    def insert(self, data):
        self._op = "insert"
        self._data = data
        return self

    def update(self, data):
        self._op = "update"
        self._data = data
        return self

    def select(self, *_args):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    async def execute(self):
        rows = self.store[self.table_name]
        if self._op == "insert":
            row = dict(self._data)
            row.setdefault("id", f"{self.table_name}-{len(rows) + 1}")
            if self.table_name == "actions":
                row.setdefault("status", "proposed")  # matches migration's DEFAULT 'proposed'
            rows.append(row)
            return _FakeResult([row])
        if self._op == "select":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            return _FakeResult(matched)
        if self._op == "update":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            for r in matched:
                r.update(self._data)
            return _FakeResult(matched)
        return _FakeResult([])


class _FakeSupabase:
    def __init__(self):
        self.store = {"actions": [], "approvals": [], "audit_log": []}

    def table(self, name):
        self.store.setdefault(name, [])
        return _FakeQuery(self.store, name)


def _run():
    import database.client as db_client
    db_client.supabase = _FakeSupabase()

    async def _check():
        # No duplicate exists yet.
        existing = await db_client.get_action_by_idempotency_key("research:posture-correctors")
        assert existing is None

        action = await db_client.create_action(
            type="create_shopify_product",
            proposing_agent="researcher",
            payload={"title": "Posture Corrector", "price": "24.99"},
            idempotency_key="research:posture-correctors",
        )
        assert action["type"] == "create_shopify_product"
        assert action["proposing_agent"] == "researcher"
        assert action["risk_level"] == "low"
        action_id = action["id"]

        # A 'proposed' audit_log entry was written.
        audit_rows = db_client.supabase.store["audit_log"]
        assert any(r["action_id"] == action_id and r["event"] == "proposed" for r in audit_rows)

        # Duplicate lookup now finds it (dedup check for the caller).
        found = await db_client.get_action_by_idempotency_key("research:posture-correctors")
        assert found is not None and found["id"] == action_id

        # Approve it.
        approval = await db_client.record_approval(action_id, "approved", decided_by="123456")
        assert approval["decision"] == "approved"
        stored_action = await db_client.get_action(action_id)
        assert stored_action["status"] == "approved"
        assert any(r["action_id"] == action_id and r["event"] == "approved" for r in audit_rows)

        # Mark it executed with a result.
        await db_client.mark_action_executed(action_id, result={"shopify_id": 999, "url": "https://x/999"})
        stored_action = await db_client.get_action(action_id)
        assert stored_action["status"] == "executed"
        assert stored_action["result"]["shopify_id"] == 999
        assert any(r["action_id"] == action_id and r["event"] == "executed" for r in audit_rows)

        # A second, separate action that gets rejected then would-be-failed.
        action2 = await db_client.create_action(
            type="update_shopify_product",
            proposing_agent="store_monitor",
            payload={"title": "New Title"},
            before={"title": "Old Title"},
        )
        await db_client.record_approval(action2["id"], "rejected", reason="title is worse")
        stored2 = await db_client.get_action(action2["id"])
        assert stored2["status"] == "rejected"
        assert any(
            r["action_id"] == action2["id"] and r["event"] == "rejected" and r["detail"]["reason"] == "title is worse"
            for r in audit_rows
        )

        await db_client.mark_action_failed(action2["id"], "shopify API returned 500")
        stored2 = await db_client.get_action(action2["id"])
        assert stored2["status"] == "failed"
        assert stored2["error"] == "shopify API returned 500"

        # Race guard: a second record_approval() call on an action that's
        # already been decided (simulating a double-tap or a redelivered
        # Telegram callback that both read 'proposed' before either wrote)
        # must return None, not record a second approval or flip anything.
        action3 = await db_client.create_action(
            type="create_shopify_product",
            proposing_agent="researcher",
            payload={"title": "Race Widget", "price": "19.99"},
        )
        first = await db_client.record_approval(action3["id"], "approved", decided_by="111")
        assert first is not None and first["decision"] == "approved"
        second = await db_client.record_approval(action3["id"], "rejected", decided_by="222")
        assert second is None, "a second decision on an already-decided action must return None"
        approval_rows = [r for r in db_client.supabase.store["approvals"] if r["action_id"] == action3["id"]]
        assert len(approval_rows) == 1, "only the winning decision should be recorded"
        stored3 = await db_client.get_action(action3["id"])
        assert stored3["status"] == "approved", "the losing call must not flip status back"

    asyncio.run(_check())
    print("approval-gate DB helper checks passed")


if __name__ == "__main__":
    _run()

# Regression check for a batch of bugs found via an external code review of
# the public repo (2026-07-21): every route in api/dashboard.py that called
# supabase.table(...).execute() directly (bypassing database/client.py's
# already-async-converted helpers) was missing `await`, since Phase 2.2
# switched to Supabase's async client where .execute() is a real coroutine.
# Also verifies the more serious finding: POST .../shopify-draft used to
# call Shopify's create_product() directly with no approval step -- it must
# now only ever propose an `actions` row and send a Telegram approval
# request, never touch Shopify directly.
# Needs fastapi+httpx+python-telegram-bot+supabase installed to run.
# Run with: python backend/tests/test_dashboard_routes.py

import asyncio
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
config.SHOPIFY_ACCESS_TOKEN = "test-token"
config.SHOPIFY_SHOP_URL = "teststore.myshopify.com"
config.TELEGRAM_BOT_TOKEN = "test-bot-token"
config.TELEGRAM_CHAT_ID = "12345"


class _UniqueViolation(Exception):
    pass


class _FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQueryBuilder:
    def __init__(self, store, table_name):
        self.store = store
        self.table_name = table_name
        self._op = None
        self._data = None
        self._filters = {}
        self._count = None

    def insert(self, data):
        self._op = "insert"
        self._data = data
        return self

    def update(self, data):
        self._op = "update"
        self._data = data
        return self

    def select(self, *_a, count=None):
        self._op = "select"
        self._count = count
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    async def execute(self):
        rows = self.store[self.table_name]
        if self._op == "insert":
            key = self._data.get("idempotency_key")
            if self.table_name == "actions" and key and any(r.get("idempotency_key") == key for r in rows):
                raise _UniqueViolation(f"duplicate key value violates unique constraint: {key}")
            row = dict(self._data)
            row.setdefault("id", f"{self.table_name}-{len(rows) + 1}")
            if self.table_name == "actions":
                row.setdefault("status", "proposed")
            rows.append(row)
            return _FakeResult([row])
        if self._op == "select":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            count = len(matched) if self._count == "exact" else None
            return _FakeResult(matched, count=count)
        if self._op == "update":
            matched = [r for r in rows if all(r.get(c) == v for c, v in self._filters.items())]
            for r in matched:
                r.update(self._data)
            return _FakeResult(matched)
        return _FakeResult([])


class _FakeSupabase:
    def __init__(self):
        self.store = {
            "products": [
                {"id": "p1", "name": "Posture Corrector", "niche": "wellness",
                 "status": "idea", "notes": "great margins", "score": 8},
            ],
            "research": [],
            "agent_tasks": [],
            "actions": [],
            "approvals": [],
            "audit_log": [],
        }

    def table(self, name):
        self.store.setdefault(name, [])
        return _FakeQueryBuilder(self.store, name)


import database.client as db_client  # noqa: E402
db_client.supabase = _FakeSupabase()

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import api.dashboard as dashboard  # noqa: E402
import tgbot.approvals as approvals  # noqa: E402

_sent_approval_requests = []


async def _fake_send_approval_request(action):
    _sent_approval_requests.append(action)


approvals.send_approval_request = _fake_send_approval_request
dashboard.limiter.enabled = False  # avoid cross-test rate-limit bucket interference

app = FastAPI()
app.state.limiter = dashboard.limiter
app.include_router(dashboard.router, prefix="/api/dashboard")
client = TestClient(app)


def test_summary_route_does_not_crash_on_the_previously_unawaited_calls():
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_products"] == 1
    assert body["products"][0]["name"] == "Posture Corrector"


def test_get_products_route_works_and_validates_status():
    r = client.get("/api/dashboard/products")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/dashboard/products?status=idea")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/dashboard/products?status=not_a_real_status")
    assert r.status_code == 422, "an unrecognised product status must be rejected, not silently ignored"


def test_get_tasks_route_validates_status_and_limit_bounds():
    r = client.get("/api/dashboard/tasks")
    assert r.status_code == 200

    r = client.get("/api/dashboard/tasks?status=bogus")
    assert r.status_code == 422

    r = client.get("/api/dashboard/tasks?limit=999999")
    assert r.status_code == 422, "limit must be bounded, not accept an arbitrary huge scan"


def test_status_update_route_validates_against_the_known_set():
    r = client.patch("/api/dashboard/products/p1/status", json={"status": "not_a_real_status"})
    assert r.status_code == 422

    r = client.patch("/api/dashboard/products/p1/status", json={"status": "active"})
    assert r.status_code == 200
    assert db_client.supabase.store["products"][0]["status"] == "active"


def test_shopify_draft_proposes_instead_of_writing_directly():
    """The critical finding: this route must never call Shopify directly --
    only ever create a proposed `actions` row and request Telegram
    approval, mirroring agents/crew.py's _propose_shopify_draft."""
    _sent_approval_requests.clear()
    r = client.post("/api/dashboard/products/p1/shopify-draft")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "proposed"
    assert body["action_id"]

    actions = db_client.supabase.store["actions"]
    assert len(actions) == 1
    action = actions[0]
    assert action["type"] == "create_shopify_product"
    assert action["proposing_agent"] == "dashboard"
    assert action["status"] == "proposed"
    assert action["payload"]["title"] == "Posture Corrector"

    assert len(_sent_approval_requests) == 1
    assert _sent_approval_requests[0]["id"] == action["id"]


def test_shopify_draft_is_idempotent_per_product():
    """A second click before the first is decided must not create a
    duplicate proposal (idempotency_key collision), and must fail cleanly
    rather than raising a raw 500."""
    r = client.post("/api/dashboard/products/p1/shopify-draft")
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    actions = [a for a in db_client.supabase.store["actions"] if a["proposing_agent"] == "dashboard"]
    assert len(actions) == 1, "must not create a second proposal for the same product"


if __name__ == "__main__":
    test_summary_route_does_not_crash_on_the_previously_unawaited_calls()
    test_get_products_route_works_and_validates_status()
    test_get_tasks_route_validates_status_and_limit_bounds()
    test_status_update_route_validates_against_the_known_set()
    test_shopify_draft_proposes_instead_of_writing_directly()
    test_shopify_draft_is_idempotent_per_product()
    print("dashboard route checks passed")

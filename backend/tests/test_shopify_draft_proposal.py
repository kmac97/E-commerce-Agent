# Regression check for Phase 1.3 (backend/agents/crew.py's
# _propose_shopify_draft). Stubs crewai/the sibling agent-creation modules
# (crewai isn't installable on this dev machine's Python), mocks the single
# httpx call (the LLM extraction step) and the Telegram send, and uses the
# same in-memory fake Supabase client pattern as the other Phase 1 tests.
# Run with: python backend/tests/test_shopify_draft_proposal.py

import asyncio
import json
import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# ── stub crewai + sibling agent modules so crew.py imports cleanly ──
crewai_stub = types.ModuleType("crewai")


class _Crew:
    def __init__(self, *a, **kw):
        pass


class _Process:
    sequential = "sequential"
    hierarchical = "hierarchical"


crewai_stub.Crew = _Crew
crewai_stub.Process = _Process
sys.modules["crewai"] = crewai_stub

for _name in ("researcher", "store_manager", "marketer", "support_agent", "analyst"):
    _mod = types.ModuleType(f"agents.{_name}")
    for _fn in (
        "create_researcher_agent", "create_research_task", "create_store_manager_agent",
        "create_marketer_agent", "create_support_agent", "create_analyst_agent",
    ):
        setattr(_mod, _fn, lambda *a, **kw: None)
    sys.modules[f"agents.{_name}"] = _mod

import config  # noqa: E402
config.SHOPIFY_ACCESS_TOKEN = "test-token"
config.SHOPIFY_SHOP_URL = "teststore.myshopify.com"
config.OPENROUTER_API_KEY = "test-key"
config.OPENROUTER_FAST_MODEL = "anthropic/claude-haiku-4.5"
config.TELEGRAM_BOT_TOKEN = "test-bot-token"
config.TELEGRAM_CHAT_ID = "12345"


# ── fake Supabase client (same shape as the other Phase 1 tests), with a
# unique-constraint check on actions.idempotency_key to mirror the real
# migration's UNIQUE column ──
class _FakeResult:
    def __init__(self, data):
        self.data = data


class _UniqueViolation(Exception):
    pass


class _FakeQueryBuilder:
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

    def select(self, *_a):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def execute(self):
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
        return _FakeQueryBuilder(self.store, name)


import database.client as db_client  # noqa: E402
db_client.supabase = _FakeSupabase()

import agents.crew as crew  # noqa: E402
import httpx  # noqa: E402
import tgbot.approvals as approvals  # noqa: E402


# ── fake httpx (the LLM extraction call, via tools/llm_client.py's call_llm,
# which checks status_code before parsing) ──
class _FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self._data


class _FakeAsyncClient:
    next_content = "{}"

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, _url, **_kw):
        return _FakeResponse({"choices": [{"message": {"content": _FakeAsyncClient.next_content}}]})


def _set_llm_response(product_dict):
    _FakeAsyncClient.next_content = json.dumps(product_dict)


httpx.AsyncClient = _FakeAsyncClient

# ── fake Telegram send, just records calls ──
_sent_approval_requests = []


async def _fake_send_approval_request(action):
    _sent_approval_requests.append(action)


approvals.send_approval_request = _fake_send_approval_request
crew.send_approval_request = _fake_send_approval_request  # in case of a cached reference


async def _run():
    # No Shopify token -> bail out immediately, no action created.
    config.SHOPIFY_ACCESS_TOKEN = ""
    result = await crew._propose_shopify_draft("task-1", "Posture Corrector", "some research text")
    assert result is None
    config.SHOPIFY_ACCESS_TOKEN = "test-token"

    # Normal path: LLM extracts clean product details -> action proposed + approval sent.
    _set_llm_response({
        "title": "Posture Corrector Pro",
        "price": "24.99",
        "description": "Fixes your posture.",
        "product_type": "Wellness",
        "tags": "posture,health",
    })
    action = await crew._propose_shopify_draft("task-1", "posture correctors", "research text here")
    assert action is not None
    assert action["type"] == "create_shopify_product"
    assert action["proposing_agent"] == "researcher"
    assert action["idempotency_key"] == "create_shopify_product:task-1"
    payload = action["payload"]
    assert payload["title"] == "Posture Corrector Pro"
    assert payload["body_html"] == "Fixes your posture."
    assert payload["variants"] == [{"price": "24.99"}]
    assert payload["status"] == "draft"
    assert len(_sent_approval_requests) == 1
    assert _sent_approval_requests[0]["id"] == action["id"]

    # Same task_id again -> idempotency key collision -> handled gracefully (None), not raised.
    result2 = await crew._propose_shopify_draft("task-1", "posture correctors", "research text here")
    assert result2 is None
    assert len(_sent_approval_requests) == 1, "must not send a second approval request for the same task_id"

    # Malformed LLM output (not valid JSON) -> handled gracefully.
    _FakeAsyncClient.next_content = "not valid json at all"
    result3 = await crew._propose_shopify_draft("task-2", "some other topic", "research text")
    assert result3 is None


if __name__ == "__main__":
    asyncio.run(_run())
    print("shopify draft proposal checks passed")

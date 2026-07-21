# Regression check for Phase 1.4 (backend/tgbot/store_monitor.py's
# optimise_product_listing). Mocks the single httpx call (the LLM rewrite
# step), fakes tools.shopify_tools.get_products, and uses the same
# in-memory fake Supabase client pattern as the rest of Phase 1.
#
# Specifically guards against the body_html/description field-name mismatch
# caught while building this: the executor passes the action payload straight
# through to Shopify's API, which expects `body_html`, not `description` --
# using the wrong key would silently no-op the description update.
# Run with: python backend/tests/test_optimise_listing_proposal.py

import asyncio
import json
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
config.SHOPIFY_ACCESS_TOKEN = "test-token"
config.SHOPIFY_SHOP_URL = "teststore.myshopify.com"
config.OPENROUTER_API_KEY = "test-key"
config.OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
config.TELEGRAM_BOT_TOKEN = "test-bot-token"
config.TELEGRAM_CHAT_ID = "12345"


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

    async def execute(self):
        rows = self.store[self.table_name]
        if self._op == "insert":
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

# tools/shopify_tools.py imports crewai.tools.BaseTool at module level for its
# CrewAI tool classes -- crewai isn't installable on this dev machine's
# Python, so stub just enough of it to let the module import.
import types  # noqa: E402
_crewai_tools_stub = types.ModuleType("crewai.tools")


class _BaseTool:
    pass


_crewai_tools_stub.BaseTool = _BaseTool
_crewai_pkg = types.ModuleType("crewai")
_crewai_pkg.tools = _crewai_tools_stub
sys.modules["crewai"] = _crewai_pkg
sys.modules["crewai.tools"] = _crewai_tools_stub

import tools.shopify_tools as shopify_tools  # noqa: E402

_FAKE_PRODUCTS = [{
    "id": "42",
    "title": "Old Boring Title",
    "body_html": "An old, boring description.",
    "variants": [{"price": "19.99"}],
}]


async def _fake_get_products(limit=250):
    return _FAKE_PRODUCTS


shopify_tools.get_products = _fake_get_products

import httpx  # noqa: E402


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


def _set_llm_response(d):
    _FakeAsyncClient.next_content = json.dumps(d)


httpx.AsyncClient = _FakeAsyncClient

import tgbot.approvals as approvals  # noqa: E402

_sent = []


async def _fake_send_approval_request(action):
    _sent.append(action)


approvals.send_approval_request = _fake_send_approval_request

import tgbot.store_monitor as store_monitor  # noqa: E402
store_monitor.send_approval_request = _fake_send_approval_request  # in case of a cached reference


async def _run():
    # No Shopify token -> bail out, no action created.
    config.SHOPIFY_ACCESS_TOKEN = ""
    msg = await store_monitor.optimise_product_listing("42")
    assert msg == "Shopify not connected."
    config.SHOPIFY_ACCESS_TOKEN = "test-token"

    # Product not found.
    msg = await store_monitor.optimise_product_listing("does-not-exist")
    assert "not found" in msg

    # Normal path: proposes an update, does not touch Shopify directly.
    _set_llm_response({"title": "Amazing New Title", "description": "A much better description."})
    msg = await store_monitor.optimise_product_listing("42")
    assert "awaiting your approval" in msg
    assert len(_sent) == 1
    action = _sent[0]
    assert action["type"] == "update_shopify_product"
    assert action["proposing_agent"] == "store_monitor"
    payload = action["payload"]
    assert payload["product_id"] == "42"
    assert payload["title"] == "Amazing New Title"
    # The field-name-mismatch guard: must be body_html, not "description",
    # since that's what the executor sends straight through to Shopify.
    assert payload["body_html"] == "A much better description."
    assert "description" not in payload
    before = action["before"]
    assert before["title"] == "Old Boring Title"
    assert before["body_html"] == "An old, boring description."

    # No idempotency_key -- re-running /optimise on the same product is
    # allowed to create a second, separate proposal.
    assert action.get("idempotency_key") is None
    msg2 = await store_monitor.optimise_product_listing("42")
    assert "awaiting your approval" in msg2
    assert len(_sent) == 2


if __name__ == "__main__":
    asyncio.run(_run())
    print("optimise listing proposal checks passed")

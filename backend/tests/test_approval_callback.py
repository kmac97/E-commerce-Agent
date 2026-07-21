# Regression check for Phase 1.2's Telegram Approve/Reject callback handler
# (backend/tgbot/approvals.py). Uses fake Telegram objects and the same
# in-memory fake Supabase client pattern as test_action_approval_client.py
# (kept local/duplicated here rather than cross-imported, so this file
# doesn't depend on another test file's internals).
# Run with: python backend/tests/test_approval_callback.py

import asyncio
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
config.TELEGRAM_BOT_TOKEN = "test-token"
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
        return _FakeQueryBuilder(self.store, name)


import database.client as db_client  # noqa: E402
db_client.supabase = _FakeSupabase()

import tgbot.approvals as approvals  # noqa: E402


class _FakeCallbackQuery:
    def __init__(self, data):
        self.data = data
        self.answers = []
        self.edits = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, **_kw):
        self.edits.append(text)


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **_kw):
        self.sent.append((chat_id, text))


def _make_update(callback_data, chat_id=12345):
    query = _FakeCallbackQuery(callback_data)
    update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=chat_id))
    return update, query


def _make_context():
    return SimpleNamespace(bot=_FakeBot())


def test_format_summary_create():
    action = {
        "type": "create_shopify_product",
        "payload": {"title": "Widget", "price": "9.99", "product_type": "Gadgets", "description": "A widget."},
    }
    text = approvals._format_action_summary(action)
    assert "Widget" in text and "9.99" in text


def test_format_summary_update_shows_diff():
    action = {
        "type": "update_shopify_product",
        "payload": {"product_id": "1", "title": "New Title"},
        "before": {"title": "Old Title"},
    }
    text = approvals._format_action_summary(action)
    assert "Old Title" in text and "New Title" in text


async def _run_async_checks():
    # Non-owner: owner_only drops it before the handler body ever runs.
    update, query = _make_update("approve:whatever", chat_id=99999)
    context = _make_context()
    await approvals.handle_approval_callback(update, context)
    assert query.answers == [], "non-owner callback must be dropped before answering"

    # Owner approves a create_shopify_product action -- executor runs.
    action = await db_client.create_action(
        type="create_shopify_product",
        proposing_agent="researcher",
        payload={"title": "Widget", "price": "9.99"},
    )

    async def fake_create_executor(_payload):
        return {"shopify_id": 555, "url": "https://x/555"}

    approvals.ACTION_EXECUTORS["create_shopify_product"] = fake_create_executor

    update, query = _make_update(f"approve:{action['id']}")
    context = _make_context()
    await approvals.handle_approval_callback(update, context)

    stored = await db_client.get_action(action["id"])
    assert stored["status"] == "executed"
    assert stored["result"]["shopify_id"] == 555
    assert any(a[0] and "Approved" in a[0] for a in query.answers)
    assert any("555" in m[1] for m in context.bot.sent)

    # Tapping Approve again on the now-executed action must NOT re-execute.
    update2, query2 = _make_update(f"approve:{action['id']}")
    context2 = _make_context()
    await approvals.handle_approval_callback(update2, context2)
    assert query2.answers and "executed" in query2.answers[0][0].lower()
    assert context2.bot.sent == [], "already-decided action must not re-execute"

    # Reject flow: records rejection, never calls an executor.
    action2 = await db_client.create_action(
        type="update_shopify_product",
        proposing_agent="store_monitor",
        payload={"product_id": "1", "title": "New"},
        before={"title": "Old"},
    )
    update3, query3 = _make_update(f"reject:{action2['id']}")
    context3 = _make_context()
    await approvals.handle_approval_callback(update3, context3)
    stored2 = await db_client.get_action(action2["id"])
    assert stored2["status"] == "rejected"
    assert context3.bot.sent == []


if __name__ == "__main__":
    test_format_summary_create()
    test_format_summary_update_shows_diff()
    print("format_action_summary checks passed")
    asyncio.run(_run_async_checks())
    print("approval callback handler checks passed")

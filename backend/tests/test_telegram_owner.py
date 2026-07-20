# Regression check for the Telegram owner restriction (backend/tgbot/auth.py).
# No telegram package needed -- is_valid/owner_only only duck-type on
# update.effective_chat.id, so a plain stub object stands in for Update.
# Run with: python backend/tests/test_telegram_owner.py

import asyncio
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
from tgbot.auth import is_owner, owner_only  # noqa: E402


def _update(chat_id):
    return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id) if chat_id is not None else None)


def test_correct_owner_allowed():
    config.TELEGRAM_CHAT_ID = "12345"
    assert is_owner(12345) is True


def test_wrong_chat_id_rejected():
    config.TELEGRAM_CHAT_ID = "12345"
    assert is_owner(99999) is False


def test_missing_chat_id_rejected():
    config.TELEGRAM_CHAT_ID = "12345"
    assert is_owner(None) is False


def test_missing_configured_owner_rejects_everyone():
    config.TELEGRAM_CHAT_ID = None
    assert is_owner(12345) is False


def test_negative_group_chat_id_matches():
    """Group chats have negative IDs -- str comparison must still work."""
    config.TELEGRAM_CHAT_ID = "-100123456"
    assert is_owner(-100123456) is True


def _run_decorator_check():
    config.TELEGRAM_CHAT_ID = "12345"
    calls = []

    @owner_only
    async def handler(update, context):
        calls.append(update.effective_chat.id)

    async def _check():
        await handler(_update(12345), None)
        assert calls == [12345], "owner's message should reach the handler"

        await handler(_update(99999), None)
        assert calls == [12345], "non-owner's message must not reach the handler"

        await handler(_update(None), None)
        assert calls == [12345], "missing chat_id must not reach the handler"

    asyncio.run(_check())
    print("owner_only decorator check passed")


if __name__ == "__main__":
    test_correct_owner_allowed()
    test_wrong_chat_id_rejected()
    test_missing_chat_id_rejected()
    test_missing_configured_owner_rejects_everyone()
    test_negative_group_chat_id_matches()
    print("is_owner tests passed")
    _run_decorator_check()

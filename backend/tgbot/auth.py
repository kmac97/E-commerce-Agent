# tgbot/auth.py
# Shared owner check for Telegram command/message handlers. Applied as a
# decorator on every handler in commands.py so the restriction lives in one
# place instead of being duplicated (and inevitably missed somewhere).

import functools
import logging

import config

logger = logging.getLogger(__name__)


def is_owner(chat_id) -> bool:
    """Compares as strings -- TELEGRAM_CHAT_ID comes from env (str), chat_id from
    Telegram (int, and negative for groups), so cast both rather than guess a type."""
    if chat_id is None or not config.TELEGRAM_CHAT_ID:
        return False
    return str(chat_id) == str(config.TELEGRAM_CHAT_ID)


def owner_only(handler):
    """Silently drops updates from anyone but config.TELEGRAM_CHAT_ID."""
    @functools.wraps(handler)
    async def wrapper(update, context):
        chat_id = update.effective_chat.id if update.effective_chat else None
        if not is_owner(chat_id):
            logger.warning(f"Ignored Telegram update from unauthorised chat_id={chat_id}")
            return
        return await handler(update, context)
    return wrapper

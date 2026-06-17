# telegram/bot.py
# Telegram bot setup and message sending.

import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

import config
from tgbot.commands import (
    cmd_start,
    cmd_help,
    cmd_research,
    cmd_products,
    cmd_tasks,
    cmd_status,
    handle_message,
)

logger = logging.getLogger(__name__)

# Global bot instance for sending messages from agents
_bot: Bot = None


async def send_telegram_message(text: str, parse_mode: str = ParseMode.MARKDOWN):
    """
    Send a message to your Telegram chat.
    Called by agents to notify you of results and updates.
    Falls back to plain text if markdown parsing fails.
    """
    global _bot
    if not _bot:
        _bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

    try:
        await _bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=parse_mode,
        )
    except Exception as e:
        # Markdown parse error — retry without formatting
        logger.warning(f"Markdown send failed ({e}), retrying as plain text")
        try:
            await _bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=None,
            )
        except Exception as e2:
            logger.error(f"Failed to send Telegram message: {e2}")


async def start_telegram_bot():
    """
    Start the Telegram bot. Runs as a background task.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")
        return

    global _bot

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    _bot = app.bot

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("research", cmd_research))
    app.add_handler(CommandHandler("products", cmd_products))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("status", cmd_status))

    # Handle plain text messages (chat with the assistant)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Telegram bot polling started")

    # Start polling (non-blocking via asyncio)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

# tgbot/approvals.py
# Telegram Approve/Reject flow for proposed actions (Phase 1 approval gate).
# Anything that writes to Shopify goes through here: propose (database.client
# .create_action), notify with inline buttons (send_approval_request), execute
# only once the owner taps Approve (handle_approval_callback).

import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config
from tgbot.auth import owner_only
from database.client import get_action, record_approval, mark_action_executed, mark_action_failed

logger = logging.getLogger(__name__)


async def _execute_create_shopify_product(payload: dict) -> dict:
    from tools.shopify_tools import create_product
    product = await create_product(payload)
    shop = config.SHOPIFY_SHOP_URL.replace("https://", "").replace("http://", "").rstrip("/")
    return {"shopify_id": product.get("id"), "url": f"https://{shop}/admin/products/{product.get('id')}"}


async def _execute_update_shopify_product(payload: dict) -> dict:
    from tools.shopify_tools import update_product
    product_id = payload["product_id"]
    updates = {k: v for k, v in payload.items() if k != "product_id"}
    product = await update_product(product_id, updates)
    return {"shopify_id": product.get("id"), "title": product.get("title")}


# Keyed by actions.type. New action types (Phase 5's ad campaigns, etc.) get
# added here -- handle_approval_callback fails cleanly if a type has none.
ACTION_EXECUTORS = {
    "create_shopify_product": _execute_create_shopify_product,
    "update_shopify_product": _execute_update_shopify_product,
}


def _format_action_summary(action: dict) -> str:
    """Human-readable Telegram message body for a proposed action."""
    payload = action.get("payload") or {}
    before = action.get("before") or {}

    if action["type"] == "create_shopify_product":
        return (
            f"🏪 *New Shopify draft proposed*\n\n"
            f"*Title:* {payload.get('title', '?')}\n"
            f"*Price:* ${payload.get('price', '?')}\n"
            f"*Type:* {payload.get('product_type') or '-'}\n\n"
            f"{payload.get('description') or payload.get('body_html') or ''}"
        )

    if action["type"] == "update_shopify_product":
        # Keys here match Shopify's own product fields (body_html, not
        # "description") -- payload is passed straight through to Shopify by
        # the executor with no translation, so this must use the same names
        # or a real field change would silently show no diff here.
        lines = [f"✍️ *Listing update proposed* (product {payload.get('product_id', '?')})\n"]
        if payload.get("title") and before.get("title") != payload.get("title"):
            lines.append(f"*Title:*\n{before.get('title', '(none)')}\n→ {payload['title']}\n")
        if payload.get("body_html") and before.get("body_html") != payload.get("body_html"):
            lines.append(f"*Description:*\n{before.get('body_html', '(none)')}\n→ {payload['body_html']}\n")
        return "\n".join(lines)

    return f"Action proposed: {action['type']}\n{payload}"


async def send_approval_request(action: dict):
    """Send a Telegram message with Approve/Reject buttons for a proposed action."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set -- cannot send approval request")
        return

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action['id']}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action['id']}"),
    ]])
    text = _format_action_summary(action)
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"Markdown send failed ({e}), retrying as plain text")
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            reply_markup=keyboard,
        )


@owner_only
async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles taps on the Approve/Reject buttons."""
    query = update.callback_query
    data = query.data or ""

    decision_raw, sep, action_id = data.partition(":")
    decision = {"approve": "approved", "reject": "rejected"}.get(decision_raw)
    if not sep or not decision or not action_id:
        await query.answer()
        return

    action = await get_action(action_id)
    if not action:
        await query.answer("Action not found (may be stale data).", show_alert=True)
        return
    if action["status"] != "proposed":
        # Already decided -- a double-tap or a stale button. Don't re-execute.
        await query.answer(f"Already {action['status']} -- no action taken.", show_alert=True)
        return

    await query.answer("Approved ✅" if decision == "approved" else "Rejected")
    approval = await record_approval(action_id, decision, decided_by=str(update.effective_chat.id))
    if approval is None:
        # Lost the race to another near-simultaneous decision on this same
        # action (double-tap, redelivered callback) -- someone else already
        # claimed it between our status check above and this call.
        await query.edit_message_text(f"⚠️ Already decided elsewhere — no action taken.")
        return

    if decision == "rejected":
        await query.edit_message_text(f"❌ Rejected: {action['type']}")
        return

    await query.edit_message_text(f"✅ Approved — executing {action['type']}...")

    executor = ACTION_EXECUTORS.get(action["type"])
    if not executor:
        await mark_action_failed(action_id, f"No executor registered for type '{action['type']}'")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ No executor for action type '{action['type']}' — marked failed.",
        )
        return

    try:
        result = await executor(action["payload"])
        await mark_action_executed(action_id, result)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Done: {result}",
        )
    except Exception as e:
        logger.error(f"Action {action_id} execution failed: {e}")
        await mark_action_failed(action_id, str(e))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Execution failed: {str(e)[:300]}",
        )

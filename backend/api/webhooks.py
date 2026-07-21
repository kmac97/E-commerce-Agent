# api/webhooks.py
# Shopify webhook receivers -- replaces store_monitor.py's periodic polling
# for new orders and low stock with real-time push notifications.
#
# Authenticated via HMAC-SHA256 (config.SHOPIFY_WEBHOOK_SECRET), not the
# X-Api-Key dependency the other routers use -- Shopify's delivery servers
# can't send that header, so this router is registered in main.py with no
# `dependencies=`. No rate limiting either: these aren't LLM/search calls
# that could burn budget, and throttling a legitimate burst of real webhook
# deliveries (e.g. many orders at once) would just mean missed alerts.
#
# See: https://shopify.dev/docs/apps/build/webhooks/verify-deliveries

import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request, Response

import config

logger = logging.getLogger(__name__)
router = APIRouter()

LOW_STOCK_THRESHOLD = 10
MAX_BODY_BYTES = 1_000_000  # Shopify payloads are small; reject anything else upfront


def _content_length_ok(request: Request) -> bool:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return True
    try:
        return int(content_length) <= MAX_BODY_BYTES
    except ValueError:
        return False


def _verify_hmac(raw_body: bytes, header_value) -> bool:
    if not header_value or not config.SHOPIFY_WEBHOOK_SECRET:
        return False
    digest = hmac.new(
        config.SHOPIFY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, header_value)


@router.post("/orders")
async def orders_webhook(request: Request):
    """orders/create -- Shopify's payload is flat REST-shaped JSON regardless
    of API version, so no GraphQL mapping is needed here."""
    if not _content_length_ok(request):
        return Response(status_code=413)
    raw = await request.body()
    if not _verify_hmac(raw, request.headers.get("x-shopify-hmac-sha256")):
        return Response(status_code=401)

    order = json.loads(raw)
    from tgbot.bot import send_telegram_message

    name = order.get("name", "?")
    total = order.get("total_price", "?")
    currency = order.get("currency", "")
    await send_telegram_message(f"🛒 *New order {name}* — ${total} {currency}")
    return Response(status_code=200)


@router.post("/inventory")
async def inventory_webhook(request: Request):
    """inventory_levels/update -- payload only carries inventory_item_id, so
    resolve it to a product/variant title via GraphQL before alerting."""
    if not _content_length_ok(request):
        return Response(status_code=413)
    raw = await request.body()
    if not _verify_hmac(raw, request.headers.get("x-shopify-hmac-sha256")):
        return Response(status_code=401)

    payload = json.loads(raw)
    available = payload.get("available")
    if available is None or available > LOW_STOCK_THRESHOLD:
        return Response(status_code=200)

    from tools.shopify_tools import get_variant_context_for_inventory_item
    from tgbot.bot import send_telegram_message

    context = None
    try:
        context = await get_variant_context_for_inventory_item(payload["inventory_item_id"])
    except Exception as e:
        logger.warning(f"Inventory webhook: couldn't resolve product title: {e}")

    emoji = "🔴" if available <= 3 else "🟡"
    if context:
        text = (
            f"{emoji} *Low stock* — {context['product_title']} "
            f"({context['variant_title']}) — {available} units left"
        )
    else:
        text = f"{emoji} *Low stock* — inventory item {payload.get('inventory_item_id')} — {available} units left"
    await send_telegram_message(text)
    return Response(status_code=200)

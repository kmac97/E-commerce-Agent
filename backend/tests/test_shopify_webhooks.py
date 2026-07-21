# Regression check for Phase 4 (api/webhooks.py's Shopify webhook
# receivers, replacing store_monitor.py's polling for new orders and low
# stock with real-time push notifications). Builds a real FastAPI app +
# TestClient (same technique as test_cors.py) and computes real HMAC
# signatures so the actual verification code path gets exercised, not a
# mocked one. Needs fastapi+httpx installed to run.
# Run with: python backend/tests/test_shopify_webhooks.py

import base64
import hashlib
import hmac
import json
import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
config.SHOPIFY_WEBHOOK_SECRET = "test-webhook-secret"

# ── fake tgbot.bot.send_telegram_message + tools.shopify_tools's inventory
# lookup, so api/webhooks.py's route bodies (which import these locally,
# per-call) pick up fakes instead of pulling in telegram/crewai/supabase ──
_sent_messages = []


async def _fake_send_telegram_message(text, parse_mode=None):
    _sent_messages.append(text)


_tgbot_bot_stub = types.ModuleType("tgbot.bot")
_tgbot_bot_stub.send_telegram_message = _fake_send_telegram_message
_tgbot_pkg = types.ModuleType("tgbot")
_tgbot_pkg.bot = _tgbot_bot_stub
sys.modules["tgbot"] = _tgbot_pkg
sys.modules["tgbot.bot"] = _tgbot_bot_stub

_lookup_result = {"value": None, "raise_error": False}


async def _fake_lookup(inventory_item_id):
    if _lookup_result["raise_error"]:
        raise RuntimeError("simulated GraphQL failure")
    return _lookup_result["value"]


_tools_shopify_stub = types.ModuleType("tools.shopify_tools")
_tools_shopify_stub.get_variant_context_for_inventory_item = _fake_lookup
_tools_pkg = types.ModuleType("tools")
_tools_pkg.shopify_tools = _tools_shopify_stub
sys.modules["tools"] = _tools_pkg
sys.modules["tools.shopify_tools"] = _tools_shopify_stub

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import api.webhooks as webhooks  # noqa: E402

app = FastAPI()
app.include_router(webhooks.router, prefix="/webhooks/shopify")
client = TestClient(app)


def _signed_headers(body: bytes, secret: str = "test-webhook-secret") -> dict:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return {"x-shopify-hmac-sha256": base64.b64encode(digest).decode()}


def test_orders_webhook_rejects_bad_signature():
    body = json.dumps({"name": "#1001", "total_price": "29.99", "currency": "USD"}).encode()
    r = client.post("/webhooks/shopify/orders", content=body, headers={"x-shopify-hmac-sha256": "bogus"})
    assert r.status_code == 401
    assert _sent_messages == []


def test_orders_webhook_accepts_valid_signature_and_notifies():
    _sent_messages.clear()
    body = json.dumps({"name": "#1001", "total_price": "29.99", "currency": "USD"}).encode()
    r = client.post("/webhooks/shopify/orders", content=body, headers=_signed_headers(body))
    assert r.status_code == 200
    assert len(_sent_messages) == 1
    assert "#1001" in _sent_messages[0]
    assert "29.99" in _sent_messages[0]


def test_inventory_webhook_ignores_healthy_stock():
    _sent_messages.clear()
    body = json.dumps({"inventory_item_id": 111, "available": 50}).encode()
    r = client.post("/webhooks/shopify/inventory", content=body, headers=_signed_headers(body))
    assert r.status_code == 200
    assert _sent_messages == []


def test_inventory_webhook_alerts_on_low_stock_with_resolved_title():
    _sent_messages.clear()
    _lookup_result["value"] = {"product_title": "Posture Corrector", "variant_title": "Default"}
    _lookup_result["raise_error"] = False
    body = json.dumps({"inventory_item_id": 111, "available": 2}).encode()
    r = client.post("/webhooks/shopify/inventory", content=body, headers=_signed_headers(body))
    assert r.status_code == 200
    assert len(_sent_messages) == 1
    assert "Posture Corrector" in _sent_messages[0]
    assert "🔴" in _sent_messages[0]  # <= 3 units gets the red emoji


def test_inventory_webhook_falls_back_when_lookup_fails():
    _sent_messages.clear()
    _lookup_result["raise_error"] = True
    body = json.dumps({"inventory_item_id": 222, "available": 5}).encode()
    r = client.post("/webhooks/shopify/inventory", content=body, headers=_signed_headers(body))
    assert r.status_code == 200
    assert len(_sent_messages) == 1
    assert "222" in _sent_messages[0]
    assert "🟡" in _sent_messages[0]  # >3 units gets the yellow emoji
    _lookup_result["raise_error"] = False


def test_missing_secret_rejects_everything():
    original = config.SHOPIFY_WEBHOOK_SECRET
    config.SHOPIFY_WEBHOOK_SECRET = None
    try:
        body = json.dumps({"name": "#1002"}).encode()
        r = client.post("/webhooks/shopify/orders", content=body, headers=_signed_headers(body, secret="anything"))
        assert r.status_code == 401
    finally:
        config.SHOPIFY_WEBHOOK_SECRET = original


if __name__ == "__main__":
    test_orders_webhook_rejects_bad_signature()
    test_orders_webhook_accepts_valid_signature_and_notifies()
    test_inventory_webhook_ignores_healthy_stock()
    test_inventory_webhook_alerts_on_low_stock_with_resolved_title()
    test_inventory_webhook_falls_back_when_lookup_fails()
    test_missing_secret_rejects_everything()
    print("shopify webhook checks passed")

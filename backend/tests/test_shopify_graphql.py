# Regression check for Phase 3 (backend/tools/shopify_tools.py's migration
# from Shopify's deprecated REST Admin API to the GraphQL Admin API).
# Verifies every convenience function still returns the same REST-shaped
# dicts callers across tgbot/, api/, agents/ already depend on, even though
# the GraphQL request/response shapes underneath are completely different
# (gid-based IDs, split product/variant creation, displayFinancialStatus
# enums, etc). Also checks the userErrors -> ShopifyGraphQLError path.
# Run with: python backend/tests/test_shopify_graphql.py

import asyncio
import json
import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# ── stub crewai.tools.BaseTool so shopify_tools.py imports cleanly (crewai
# isn't installable on this dev machine's Python) ──
_crewai_tools_stub = types.ModuleType("crewai.tools")


class _BaseTool:
    pass


_crewai_tools_stub.BaseTool = _BaseTool
_crewai_pkg = types.ModuleType("crewai")
_crewai_pkg.tools = _crewai_tools_stub
sys.modules["crewai"] = _crewai_pkg
sys.modules["crewai.tools"] = _crewai_tools_stub

import config  # noqa: E402
config.SHOPIFY_ACCESS_TOKEN = "test-token"
config.SHOPIFY_SHOP_URL = "teststore.myshopify.com"
config.SHOPIFY_API_VERSION = "2026-07"

import httpx  # noqa: E402
import tools.shopify_tools as shopify_tools  # noqa: E402


class _FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = json.dumps(data)

    def json(self):
        return self._data


class _FakeAsyncClient:
    """Routes based on which query/mutation the request body carries, so one
    fake client can serve every operation (and multi-step ones like
    create_product's productCreate -> productVariantsBulkUpdate)."""
    next_status = 200
    next_errors = None  # transport-level `errors`

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, _url, json=None, **_kw):
        if _FakeAsyncClient.next_errors is not None:
            return _FakeResponse({"errors": _FakeAsyncClient.next_errors}, status_code=200)
        if _FakeAsyncClient.next_status != 200:
            return _FakeResponse({}, status_code=_FakeAsyncClient.next_status)

        query = json["query"]
        variables = json.get("variables") or {}

        if "query GetProducts" in query:
            return _FakeResponse({"data": {"products": {"edges": [
                {"node": {
                    "legacyResourceId": "111",
                    "title": "Posture Corrector",
                    "status": "ACTIVE",
                    "descriptionHtml": "<p>Great posture.</p>",
                    "variants": {"edges": [{"node": {"price": "24.99"}}]},
                }},
            ]}}})

        if "query GetOrders" in query:
            _FakeAsyncClient.last_orders_query = variables.get("query")
            return _FakeResponse({"data": {"orders": {"edges": [
                {"node": {
                    "number": 1042,
                    "totalPriceSet": {"shopMoney": {"amount": "59.98", "currencyCode": "GBP"}},
                    "displayFinancialStatus": "PARTIALLY_PAID",
                    "createdAt": "2026-07-20T10:00:00Z",
                }},
            ]}}})

        if "query GetInventory" in query:
            return _FakeResponse({"data": {"products": {"edges": [
                {"node": {
                    "legacyResourceId": "222",
                    "title": "Low Stock Widget",
                    "variants": {"edges": [
                        {"node": {"title": "Default Title", "price": "9.99", "inventoryQuantity": 3}},
                        {"node": {"title": "Large", "price": "12.99", "inventoryQuantity": 50}},
                    ]},
                }},
            ]}}})

        if "mutation CreateProduct" in query:
            return _FakeResponse({"data": {"productCreate": {
                "product": {
                    "legacyResourceId": "333",
                    "title": variables["product"]["title"],
                    "status": variables["product"]["status"],
                    "variants": {"edges": [{"node": {"id": "gid://shopify/ProductVariant/999", "price": "0.00"}}]},
                },
                "userErrors": [],
            }}})

        if "mutation UpdateVariantPrice" in query:
            new_price = variables["variants"][0]["price"]
            return _FakeResponse({"data": {"productVariantsBulkUpdate": {
                "productVariants": [{"id": "gid://shopify/ProductVariant/999", "price": new_price}],
                "userErrors": [],
            }}})

        if "mutation UpdateProduct" in query:
            p = variables["product"]
            return _FakeResponse({"data": {"productUpdate": {
                "product": {
                    "legacyResourceId": p["id"].rsplit("/", 1)[-1],
                    "title": p.get("title", "Existing Title"),
                    "status": p.get("status", "DRAFT"),
                },
                "userErrors": [],
            }}})

        raise AssertionError(f"unexpected query in test: {query[:60]}")


def _reset():
    _FakeAsyncClient.next_status = 200
    _FakeAsyncClient.next_errors = None


httpx.AsyncClient = _FakeAsyncClient


async def _run():
    _reset()

    # get_products: GraphQL enum/gid shapes mapped back to REST-like dict.
    products = await shopify_tools.get_products(limit=50)
    assert products == [{
        "id": "111",
        "title": "Posture Corrector",
        "status": "active",
        "body_html": "<p>Great posture.</p>",
        "variants": [{"price": "24.99"}],
    }]

    # get_orders: number/totalPriceSet/displayFinancialStatus mapped to
    # order_number/total_price/financial_status; status="any" sends no filter.
    orders = await shopify_tools.get_orders(status="any", limit=10)
    assert orders == [{
        "order_number": 1042,
        "total_price": "59.98",
        "financial_status": "partially_paid",
        "created_at": "2026-07-20T10:00:00Z",
        "currency": "GBP",
    }]
    assert _FakeAsyncClient.last_orders_query is None

    # created_at_min gets folded into the query filter string.
    await shopify_tools.get_orders(status="any", limit=10, created_at_min="2026-07-19T00:00:00Z")
    assert _FakeAsyncClient.last_orders_query == "created_at:>=2026-07-19T00:00:00Z"

    await shopify_tools.get_orders(status="open", limit=10)
    assert _FakeAsyncClient.last_orders_query == "status:open"

    # get_orders_summary: aggregates get_orders() output.
    summary = await shopify_tools.get_orders_summary()
    assert summary == {"total_orders": 1, "total_revenue": 59.98, "currency": "GBP"}

    # get_inventory: filters by threshold, keeps the one low-stock variant.
    low = await shopify_tools.get_inventory(threshold=10)
    assert low == [{
        "product_id": "222",
        "title": "Low Stock Widget",
        "variant": "Default Title",
        "quantity": 3,
        "price": "9.99",
    }]

    # create_product: productCreate (no inline variants) then
    # productVariantsBulkUpdate sets the real price on the default variant.
    created = await shopify_tools.create_product({
        "title": "New Gadget",
        "body_html": "<p>Shiny.</p>",
        "product_type": "Gadgets",
        "tags": "new, trending",
        "variants": [{"price": "34.99"}],
        "status": "draft",
    })
    assert created == {"id": "333", "title": "New Gadget", "variants": [{"price": "34.99"}]}

    # create_product with no variants/price at all (dashboard.py's draft-push
    # path) -- must not attempt a price update, and must not crash.
    created_no_price = await shopify_tools.create_product({
        "title": "No Price Yet",
        "body_html": "",
        "status": "draft",
    })
    assert created_no_price == {"id": "333", "title": "No Price Yet", "variants": []}

    # update_product: body_html -> descriptionHtml, status -> upper enum,
    # response mapped back to lowercase status + bare numeric id.
    updated = await shopify_tools.update_product("333", {"title": "Renamed", "status": "active"})
    assert updated == {"id": "333", "title": "Renamed", "status": "active"}

    # userErrors on a mutation raise ShopifyGraphQLError (not silently ignored).
    orig_post = _FakeAsyncClient.post

    async def _post_with_user_errors(self, _url, json=None, **kw):
        if "mutation UpdateProduct" in json["query"]:
            return _FakeResponse({"data": {"productUpdate": {
                "product": None,
                "userErrors": [{"field": ["status"], "message": "Invalid status"}],
            }}})
        return await orig_post(self, _url, json=json, **kw)

    _FakeAsyncClient.post = _post_with_user_errors
    try:
        raised = False
        try:
            await shopify_tools.update_product("333", {"status": "bogus"})
        except shopify_tools.ShopifyGraphQLError:
            raised = True
        assert raised, "userErrors on a mutation must raise ShopifyGraphQLError"
    finally:
        _FakeAsyncClient.post = orig_post

    # Transport-level errors (bad status code / GraphQL `errors` array) raise too.
    _FakeAsyncClient.next_status = 500
    try:
        raised = False
        try:
            await shopify_tools.get_products(limit=5)
        except shopify_tools.ShopifyGraphQLError:
            raised = True
        assert raised
    finally:
        _reset()

    _FakeAsyncClient.next_errors = [{"message": "Throttled"}]
    try:
        raised = False
        try:
            await shopify_tools.get_products(limit=5)
        except shopify_tools.ShopifyGraphQLError:
            raised = True
        assert raised
    finally:
        _reset()

    # CrewAI BaseTool wrappers delegate to the same functions and format a
    # human-readable string -- spot-check one read tool and one write tool.
    tool_output = await shopify_tools.GetProductsTool()._async_run(limit=50)
    assert "[111] Posture Corrector | $24.99 | active" in tool_output

    update_tool_output = await shopify_tools.UpdateProductTool()._async_run(
        "333", title="Renamed", description=None, status="active"
    )
    assert update_tool_output == "✅ Product 333 updated: Renamed | active"


if __name__ == "__main__":
    asyncio.run(_run())
    print("shopify GraphQL migration checks passed")

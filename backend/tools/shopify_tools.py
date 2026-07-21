# tools/shopify_tools.py
# Shopify API tools for the Store Manager agent.
# Implemented as CrewAI BaseTool subclasses so agents can call them directly.
#
# Uses the GraphQL Admin API -- REST's /products and /variants endpoints
# have been deprecated since API version 2024-04. Every function below
# keeps its original REST-shaped input/output contract (dict keys like
# body_html, variants[0].price, order_number, financial_status) so the
# rest of the codebase (tgbot/, api/, agents/) didn't need to change --
# only the HTTP mechanics underneath moved to GraphQL.

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import config


# ─── GRAPHQL HELPERS ───────────────────────────

class ShopifyGraphQLError(Exception):
    pass


def graphql_url() -> str:
    return f"https://{config.SHOPIFY_SHOP_URL}/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json"


def get_headers() -> dict:
    return {
        "X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


def _product_gid(product_id) -> str:
    s = str(product_id)
    return s if s.startswith("gid://") else f"gid://shopify/Product/{s}"


async def graphql_request(query: str, variables: dict = None) -> dict:
    """POST a query/mutation to Shopify's GraphQL Admin API. Raises
    ShopifyGraphQLError on a non-200 or a transport-level `errors` array --
    mutation-level `userErrors` are shaped differently per mutation, so
    callers check those themselves."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(
            graphql_url(),
            json={"query": query, "variables": variables or {}},
            headers=get_headers(),
        )
    if res.status_code != 200:
        raise ShopifyGraphQLError(f"{res.status_code} {res.text}")
    body = res.json()
    if "errors" in body:
        raise ShopifyGraphQLError(str(body["errors"]))
    return body["data"]


# ─── GET PRODUCTS TOOL ─────────────────────────

_PRODUCTS_QUERY = """
query GetProducts($first: Int!) {
  products(first: $first) {
    edges {
      node {
        legacyResourceId
        title
        status
        descriptionHtml
        variants(first: 1) {
          edges { node { price } }
        }
      }
    }
  }
}
"""


def _map_product(node: dict) -> dict:
    variant_edges = node.get("variants", {}).get("edges", [])
    variants = [{"price": variant_edges[0]["node"]["price"]}] if variant_edges else []
    return {
        "id": str(node["legacyResourceId"]),
        "title": node["title"],
        "status": (node.get("status") or "").lower(),
        "body_html": node.get("descriptionHtml") or "",
        "variants": variants,
    }


class GetProductsTool(BaseTool):
    name: str = "get_shopify_products"
    description: str = (
        "Get all products currently listed on the Shopify store. "
        "Returns product titles, prices, status (active/draft), and IDs."
    )

    def _run(self, limit: int = 50) -> str:
        import asyncio
        return asyncio.run(self._async_run(limit))

    async def _async_run(self, limit: int = 50) -> str:
        try:
            products = await get_products(limit)
        except ShopifyGraphQLError as e:
            return f"Error fetching products: {e}"
        if not products:
            return "No products found in the store."
        lines = [f"Found {len(products)} products:"]
        for p in products:
            price = p["variants"][0]["price"] if p.get("variants") else "?"
            lines.append(f"- [{p['id']}] {p['title']} | ${price} | {p['status']}")
        return "\n".join(lines)


# ─── CREATE PRODUCT TOOL ───────────────────────

_PRODUCT_CREATE_MUTATION = """
mutation CreateProduct($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product {
      legacyResourceId
      title
      status
      variants(first: 1) {
        edges { node { id price } }
      }
    }
    userErrors { field message }
  }
}
"""

_VARIANT_PRICE_MUTATION = """
mutation UpdateVariantPrice($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price }
    userErrors { field message }
  }
}
"""


class CreateProductInput(BaseModel):
    title: str = Field(description="Product title")
    description: str = Field(description="Product description in HTML or plain text")
    price: str = Field(description="Selling price as a string, e.g. '29.99'")
    vendor: str = Field(default="", description="Brand or vendor name")
    product_type: str = Field(default="", description="Product category/type")
    tags: str = Field(default="", description="Comma-separated tags")


class CreateProductTool(BaseTool):
    name: str = "create_shopify_product"
    description: str = (
        "Create a new product listing on Shopify as a draft. "
        "Use this after researching a product to add it to the store. "
        "Always creates as draft so you can review before publishing."
    )
    args_schema: type[BaseModel] = CreateProductInput

    def _run(self, title: str, description: str, price: str,
             vendor: str = "", product_type: str = "", tags: str = "") -> str:
        import asyncio
        return asyncio.run(self._async_run(title, description, price, vendor, product_type, tags))

    async def _async_run(self, title: str, description: str, price: str,
                          vendor: str, product_type: str, tags: str) -> str:
        payload = {
            "title": title,
            "body_html": description,
            "vendor": vendor,
            "product_type": product_type,
            "tags": tags,
            "variants": [{"price": price}],
            "status": "draft",
        }
        try:
            product = await create_product(payload)
        except ShopifyGraphQLError as e:
            return f"Error creating product: {e}"
        price_out = product["variants"][0]["price"] if product.get("variants") else "?"
        return (
            f"✅ Product created as draft:\n"
            f"  ID: {product['id']}\n"
            f"  Title: {product['title']}\n"
            f"  Price: ${price_out}\n"
            f"  URL: https://{config.SHOPIFY_SHOP_URL}/admin/products/{product['id']}"
        )


# ─── GET ORDERS TOOL ───────────────────────────

_ORDERS_QUERY = """
query GetOrders($first: Int!, $query: String) {
  orders(first: $first, query: $query, sortKey: PROCESSED_AT, reverse: true) {
    edges {
      node {
        number
        totalPriceSet { shopMoney { amount currencyCode } }
        displayFinancialStatus
        createdAt
      }
    }
  }
}
"""


def _map_order(node: dict) -> dict:
    money = node.get("totalPriceSet", {}).get("shopMoney", {}) or {}
    return {
        "order_number": node.get("number"),
        "total_price": money.get("amount", "0"),
        "financial_status": (node.get("displayFinancialStatus") or "").lower(),
        "created_at": node.get("createdAt"),
        "currency": money.get("currencyCode", "USD"),
    }


class GetOrdersTool(BaseTool):
    name: str = "get_shopify_orders"
    description: str = (
        "Get recent orders from the Shopify store. "
        "Returns order count, revenue, and order details."
    )

    def _run(self, status: str = "any", limit: int = 20) -> str:
        import asyncio
        return asyncio.run(self._async_run(status, limit))

    async def _async_run(self, status: str = "any", limit: int = 20) -> str:
        try:
            orders = await get_orders(status, limit)
        except ShopifyGraphQLError as e:
            return f"Error fetching orders: {e}"
        if not orders:
            return "No orders found."
        total = sum(float(o.get("total_price", 0)) for o in orders)
        lines = [f"Found {len(orders)} orders | Total revenue: ${total:.2f}"]
        for o in orders[:10]:
            lines.append(
                f"- #{o['order_number']} | ${o['total_price']} | {o['financial_status']} | {o['created_at'][:10]}"
            )
        return "\n".join(lines)


# ─── UPDATE PRODUCT TOOL ───────────────────────

_PRODUCT_UPDATE_MUTATION = """
mutation UpdateProduct($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product {
      legacyResourceId
      title
      status
    }
    userErrors { field message }
  }
}
"""


class UpdateProductInput(BaseModel):
    product_id: str = Field(description="Shopify product ID to update")
    title: Optional[str] = Field(default=None, description="New product title")
    description: Optional[str] = Field(default=None, description="New product description")
    status: Optional[str] = Field(default=None, description="Product status: active, draft, or archived")


class UpdateProductTool(BaseTool):
    name: str = "update_shopify_product"
    description: str = (
        "Update an existing product on Shopify. "
        "Can update the title, description, or status (active/draft/archived)."
    )
    args_schema: type[BaseModel] = UpdateProductInput

    def _run(self, product_id: str, title: str = None,
             description: str = None, status: str = None) -> str:
        import asyncio
        return asyncio.run(self._async_run(product_id, title, description, status))

    async def _async_run(self, product_id: str, title, description, status) -> str:
        updates = {}
        if title:
            updates["title"] = title
        if description:
            updates["body_html"] = description
        if status:
            updates["status"] = status

        if not updates:
            return "No updates provided."

        try:
            product = await update_product(product_id, updates)
        except ShopifyGraphQLError as e:
            return f"Error updating product: {e}"
        return f"✅ Product {product['id']} updated: {product['title']} | {product['status']}"


# ─── INVENTORY TOOL ───────────────────────────

_INVENTORY_QUERY = """
query GetInventory($first: Int!) {
  products(first: $first) {
    edges {
      node {
        legacyResourceId
        title
        variants(first: 100) {
          edges {
            node {
              title
              price
              inventoryQuantity
            }
          }
        }
      }
    }
  }
}
"""


class GetInventoryTool(BaseTool):
    name: str = "get_shopify_inventory"
    description: str = (
        "Get inventory levels for all products. "
        "Returns products with their stock quantities. "
        "Use to check for low stock items."
    )

    def _run(self, low_stock_threshold: int = 10) -> str:
        import asyncio
        return asyncio.run(self._async_run(low_stock_threshold))

    async def _async_run(self, low_stock_threshold: int = 10) -> str:
        try:
            low = await get_inventory(low_stock_threshold)
        except ShopifyGraphQLError as e:
            return f"Error fetching inventory: {e}"
        if not low:
            return f"All products have stock above {low_stock_threshold} units."
        lines = [
            f"- {item['title']} (variant: {item['variant']}) — {item['quantity']} left"
            for item in low
        ]
        return f"⚠️ Low stock ({len(low)} items):\n" + "\n".join(lines)


# ─── CONVENIENCE FUNCTIONS (for API routes, tgbot commands, agents) ────

async def get_products(limit: int = 50) -> list:
    data = await graphql_request(_PRODUCTS_QUERY, {"first": limit})
    return [_map_product(e["node"]) for e in data["products"]["edges"]]


async def get_orders(status: str = "any", limit: int = 50, created_at_min: str = None) -> list:
    terms = []
    if status and status != "any":
        terms.append(f"status:{status}")
    if created_at_min:
        terms.append(f"created_at:>={created_at_min}")
    variables = {"first": limit, "query": " ".join(terms) if terms else None}
    data = await graphql_request(_ORDERS_QUERY, variables)
    return [_map_order(e["node"]) for e in data["orders"]["edges"]]


async def get_inventory(threshold: int = 10) -> list:
    """Return products below the stock threshold. Uses ProductVariant.
    inventoryQuantity (a sellable-quantity total across all locations) --
    the cheap equivalent of REST's flat inventory_quantity. Switch to the
    InventoryItem/InventoryLevel connection only if per-location numbers
    are ever actually needed."""
    data = await graphql_request(_INVENTORY_QUERY, {"first": 250})
    low = []
    for edge in data["products"]["edges"]:
        node = edge["node"]
        for v_edge in node.get("variants", {}).get("edges", []):
            v = v_edge["node"]
            qty = v.get("inventoryQuantity")
            if qty is not None and qty <= threshold:
                low.append({
                    "product_id": str(node["legacyResourceId"]),
                    "title": node["title"],
                    "variant": v.get("title") or "Default",
                    "quantity": qty,
                    "price": v.get("price"),
                })
    return low


async def create_product(payload: dict) -> dict:
    """Create a new Shopify product. payload uses the same REST-shaped keys
    the rest of the codebase already builds (title, body_html, vendor,
    product_type, tags, variants[0].price, status) -- translated here to
    GraphQL's ProductCreateInput, since productCreate no longer accepts
    variants inline (the initial variant's price has to be set separately
    via productVariantsBulkUpdate).

    Note: products created this way are unpublished on all sales channels
    by default (a GraphQL behavior change vs classic REST). Since this
    function is only ever called to create DRAFT proposals awaiting human
    approval, that's the desired behavior already -- no publish step is
    added here. If a future "go live" flow activates a product, it'll need
    its own `publishablePublish` call to actually appear on the Online
    Store channel.
    """
    product_input = {
        "title": payload.get("title", ""),
        "descriptionHtml": payload.get("body_html", ""),
        "status": (payload.get("status") or "draft").upper(),
    }
    if payload.get("vendor"):
        product_input["vendor"] = payload["vendor"]
    if payload.get("product_type"):
        product_input["productType"] = payload["product_type"]
    tags = payload.get("tags") or ""
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    if tags_list:
        product_input["tags"] = tags_list

    data = await graphql_request(_PRODUCT_CREATE_MUTATION, {"product": product_input})
    result = data["productCreate"]
    if result["userErrors"]:
        raise ShopifyGraphQLError(str(result["userErrors"]))

    product = result["product"]
    variant_edges = product.get("variants", {}).get("edges", [])
    variants_in = payload.get("variants") or []
    price = None
    if variants_in and variant_edges:
        price = variants_in[0].get("price")
        variant_gid = variant_edges[0]["node"]["id"]
        price_data = await graphql_request(_VARIANT_PRICE_MUTATION, {
            "productId": f"gid://shopify/Product/{product['legacyResourceId']}",
            "variants": [{"id": variant_gid, "price": price}],
        })
        price_result = price_data["productVariantsBulkUpdate"]
        if price_result["userErrors"]:
            raise ShopifyGraphQLError(str(price_result["userErrors"]))
        price = price_result["productVariants"][0]["price"]

    return {
        "id": str(product["legacyResourceId"]),
        "title": product["title"],
        "variants": [{"price": price}] if price is not None else [],
    }


async def update_product(product_id, updates: dict) -> dict:
    """Update a Shopify product by ID. updates dict can include title,
    body_html, status -- same REST-shaped keys as before, translated here
    to GraphQL's ProductUpdateInput."""
    product_input = {"id": _product_gid(product_id)}
    if updates.get("title"):
        product_input["title"] = updates["title"]
    if updates.get("body_html"):
        product_input["descriptionHtml"] = updates["body_html"]
    if updates.get("status"):
        product_input["status"] = updates["status"].upper()

    data = await graphql_request(_PRODUCT_UPDATE_MUTATION, {"product": product_input})
    result = data["productUpdate"]
    if result["userErrors"]:
        raise ShopifyGraphQLError(str(result["userErrors"]))

    product = result["product"]
    return {
        "id": str(product["legacyResourceId"]),
        "title": product["title"],
        "status": (product.get("status") or "").lower(),
    }


async def get_orders_summary() -> dict:
    # Note: Shopify's `read_orders` scope only returns orders from the last
    # 60 days by default (a platform-wide restriction, not specific to
    # GraphQL) -- `read_all_orders` needs a one-time Partner Dashboard
    # approval if full order history is ever needed here.
    orders = await get_orders(status="any", limit=250)
    total_revenue = sum(float(o.get("total_price", 0)) for o in orders)
    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "currency": orders[0].get("currency", "USD") if orders else "USD",
    }

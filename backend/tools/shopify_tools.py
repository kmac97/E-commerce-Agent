# tools/shopify_tools.py
# Shopify API tools for the Store Manager agent.
# Implemented as CrewAI BaseTool subclasses so agents can call them directly.

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import config


# ─── HELPERS ───────────────────────────────────

def get_headers() -> dict:
    return {
        "X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


def shopify_url(endpoint: str) -> str:
    return f"https://{config.SHOPIFY_SHOP_URL}/admin/api/{config.SHOPIFY_API_VERSION}/{endpoint}"


# ─── GET PRODUCTS TOOL ─────────────────────────

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
        async with httpx.AsyncClient() as client:
            res = await client.get(
                shopify_url(f"products.json?limit={limit}"),
                headers=get_headers(),
            )
            if res.status_code != 200:
                return f"Error fetching products: {res.status_code} {res.text}"
            products = res.json().get("products", [])
            if not products:
                return "No products found in the store."
            lines = [f"Found {len(products)} products:"]
            for p in products:
                price = p.get("variants", [{}])[0].get("price", "?")
                lines.append(f"- [{p['id']}] {p['title']} | ${price} | {p['status']}")
            return "\n".join(lines)


# ─── CREATE PRODUCT TOOL ───────────────────────

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
            "product": {
                "title": title,
                "body_html": description,
                "vendor": vendor,
                "product_type": product_type,
                "tags": tags,
                "variants": [{"price": price}],
                "status": "draft",
            }
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(
                shopify_url("products.json"),
                json=payload,
                headers=get_headers(),
            )
            if res.status_code not in (200, 201):
                return f"Error creating product: {res.status_code} {res.text}"
            product = res.json().get("product", {})
            return (
                f"✅ Product created as draft:\n"
                f"  ID: {product['id']}\n"
                f"  Title: {product['title']}\n"
                f"  Price: ${product['variants'][0]['price']}\n"
                f"  URL: https://{config.SHOPIFY_SHOP_URL}/admin/products/{product['id']}"
            )


# ─── GET ORDERS TOOL ───────────────────────────

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
        async with httpx.AsyncClient() as client:
            res = await client.get(
                shopify_url(f"orders.json?status={status}&limit={limit}"),
                headers=get_headers(),
            )
            if res.status_code != 200:
                return f"Error fetching orders: {res.status_code} {res.text}"
            orders = res.json().get("orders", [])
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

        async with httpx.AsyncClient() as client:
            res = await client.put(
                shopify_url(f"products/{product_id}.json"),
                json={"product": updates},
                headers=get_headers(),
            )
            if res.status_code != 200:
                return f"Error updating product: {res.status_code} {res.text}"
            product = res.json().get("product", {})
            return f"✅ Product {product['id']} updated: {product['title']} | {product['status']}"


# ─── INVENTORY TOOL ───────────────────────────

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
        async with httpx.AsyncClient() as client:
            res = await client.get(
                shopify_url("products.json?limit=250"),
                headers=get_headers(),
            )
            if res.status_code != 200:
                return f"Error fetching inventory: {res.status_code}"
            products = res.json().get("products", [])
            low = []
            for p in products:
                for v in p.get("variants", []):
                    qty = v.get("inventory_quantity", 0)
                    if qty is not None and qty <= low_stock_threshold:
                        low.append(f"- {p['title']} (variant: {v.get('title','')}) — {qty} left")
            if not low:
                return f"All products have stock above {low_stock_threshold} units."
            return f"⚠️ Low stock ({len(low)} items):\n" + "\n".join(low)


# ─── CONVENIENCE FUNCTIONS (for API routes) ────

async def get_products(limit: int = 50) -> list:
    async with httpx.AsyncClient() as client:
        res = await client.get(
            shopify_url(f"products.json?limit={limit}"),
            headers=get_headers(),
        )
        res.raise_for_status()
        return res.json().get("products", [])


async def get_orders(status: str = "any", limit: int = 50) -> list:
    async with httpx.AsyncClient() as client:
        res = await client.get(
            shopify_url(f"orders.json?status={status}&limit={limit}"),
            headers=get_headers(),
        )
        res.raise_for_status()
        return res.json().get("orders", [])


async def get_inventory(threshold: int = 10) -> list:
    """Return products below the stock threshold."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            shopify_url("products.json?limit=250"),
            headers=get_headers(),
        )
        res.raise_for_status()
        products = res.json().get("products", [])
        low = []
        for p in products:
            for v in p.get("variants", []):
                qty = v.get("inventory_quantity")
                if qty is not None and qty <= threshold:
                    low.append({
                        "product_id": p["id"],
                        "title": p["title"],
                        "variant": v.get("title", "Default"),
                        "quantity": qty,
                        "price": v.get("price"),
                    })
        return low


async def create_product(payload: dict) -> dict:
    """Create a new Shopify product. payload maps directly to Shopify's product
    fields (title, body_html, product_type, tags, variants, status, etc.)."""
    async with httpx.AsyncClient() as client:
        res = await client.post(
            shopify_url("products.json"),
            json={"product": payload},
            headers=get_headers(),
        )
        res.raise_for_status()
        return res.json().get("product", {})


async def update_product(product_id: str, updates: dict) -> dict:
    """Update a Shopify product by ID. updates dict can include title, body_html, variants etc."""
    async with httpx.AsyncClient() as client:
        res = await client.put(
            shopify_url(f"products/{product_id}.json"),
            json={"product": updates},
            headers=get_headers(),
        )
        res.raise_for_status()
        return res.json().get("product", {})


async def get_orders_summary() -> dict:
    orders = await get_orders(status="any", limit=250)
    total_revenue = sum(float(o.get("total_price", 0)) for o in orders)
    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "currency": orders[0].get("currency", "USD") if orders else "USD",
    }

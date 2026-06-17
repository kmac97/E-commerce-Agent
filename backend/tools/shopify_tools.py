# tools/shopify_tools.py
# Shopify API tools for the Store Manager agent.
# Phase 3: These will be fully implemented with real API calls.

import httpx
import config


def get_shopify_headers() -> dict:
    return {
        "X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


def shopify_url(endpoint: str) -> str:
    return f"https://{config.SHOPIFY_SHOP_URL}/admin/api/{config.SHOPIFY_API_VERSION}/{endpoint}"


# ─── PRODUCTS ──────────────────────────────────

async def get_products(limit: int = 50) -> list:
    """Get all products from the Shopify store."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            shopify_url(f"products.json?limit={limit}"),
            headers=get_shopify_headers(),
        )
        res.raise_for_status()
        return res.json().get("products", [])


async def create_product(title: str, body_html: str, vendor: str,
                          price: str, sku: str = None) -> dict:
    """Create a new product listing on Shopify."""
    payload = {
        "product": {
            "title": title,
            "body_html": body_html,
            "vendor": vendor,
            "variants": [{"price": price, "sku": sku or ""}],
            "status": "draft",  # Always draft first — review before publishing
        }
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(
            shopify_url("products.json"),
            json=payload,
            headers=get_shopify_headers(),
        )
        res.raise_for_status()
        return res.json().get("product", {})


async def update_product(product_id: str, updates: dict) -> dict:
    """Update an existing product."""
    async with httpx.AsyncClient() as client:
        res = await client.put(
            shopify_url(f"products/{product_id}.json"),
            json={"product": updates},
            headers=get_shopify_headers(),
        )
        res.raise_for_status()
        return res.json().get("product", {})


# ─── ORDERS ────────────────────────────────────

async def get_orders(status: str = "open", limit: int = 50) -> list:
    """Get orders from Shopify."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            shopify_url(f"orders.json?status={status}&limit={limit}"),
            headers=get_shopify_headers(),
        )
        res.raise_for_status()
        return res.json().get("orders", [])


async def get_orders_summary() -> dict:
    """Get a summary of today's orders."""
    orders = await get_orders(status="any", limit=250)
    total_revenue = sum(float(o.get("total_price", 0)) for o in orders)
    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "currency": orders[0].get("currency", "USD") if orders else "USD",
    }


# ─── INVENTORY ─────────────────────────────────

async def get_inventory_levels(location_id: str = None) -> list:
    """Get inventory levels across the store."""
    url = shopify_url("inventory_levels.json")
    if location_id:
        url += f"?location_ids={location_id}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=get_shopify_headers())
        res.raise_for_status()
        return res.json().get("inventory_levels", [])

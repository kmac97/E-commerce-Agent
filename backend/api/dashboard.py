# api/dashboard.py
# Endpoints that power the web dashboard.

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ProductCreate(BaseModel):
    name: str
    niche: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None
    cost_estimate: Optional[float] = None
    sell_price_estimate: Optional[float] = None
    margin_estimate: Optional[float] = None


@router.get("/summary")
async def get_dashboard_summary():
    """
    Returns a summary of everything for the dashboard home page.
    Product ideas, recent research, agent activity, task status.
    """
    from database.client import supabase

    # Recent research
    research = supabase.table("research").select("*").order(
        "created_at", desc=True
    ).limit(5).execute()

    # Recent agent tasks
    tasks = supabase.table("agent_tasks").select("*").order(
        "created_at", desc=True
    ).limit(10).execute()

    # Product pipeline
    products = supabase.table("products").select("*").order(
        "created_at", desc=True
    ).limit(10).execute()

    return {
        "recent_research": research.data,
        "recent_tasks": tasks.data,
        "products": products.data,
    }


@router.get("/products")
async def get_products(status: str = None):
    """Get all products, optionally filtered by status."""
    from database.client import supabase
    query = supabase.table("products").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data


@router.post("/products")
async def create_product(product: ProductCreate):
    """Manually add a product to the pipeline."""
    from database.client import save_product
    result = await save_product(
        name=product.name,
        niche=product.niche,
        score=product.score,
        notes=product.notes,
    )
    return result


@router.patch("/products/{product_id}")
async def update_product_endpoint(product_id: str, body: ProductUpdate):
    """Update product fields (name, niche, score, notes, cost/price estimates)."""
    from database.client import update_product_fields
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if fields:
        await update_product_fields(product_id, fields)
    return {"status": "updated"}


@router.patch("/products/{product_id}/status")
async def update_product_status_endpoint(product_id: str, body: StatusUpdate):
    """Update a product's pipeline status."""
    from database.client import update_product_status
    await update_product_status(product_id, body.status)
    return {"status": "updated"}


@router.delete("/products/{product_id}")
async def delete_product_item(product_id: str):
    """Delete a product from the pipeline."""
    from database.client import delete_product
    await delete_product(product_id)
    return {"status": "deleted"}


@router.post("/products/{product_id}/shopify-draft")
async def create_shopify_draft(product_id: str):
    """Push a product to Shopify as a draft listing."""
    import httpx
    import config
    from database.client import supabase

    if not config.SHOPIFY_ACCESS_TOKEN or not config.SHOPIFY_SHOP_URL:
        return {"error": "Shopify not configured — add SHOPIFY_ACCESS_TOKEN and SHOPIFY_STORE_URL to .env"}

    result = supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")

    p = result.data[0]
    shop = config.SHOPIFY_SHOP_URL.replace("https://", "").replace("http://", "").rstrip("/")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"https://{shop}/admin/api/{config.SHOPIFY_API_VERSION}/products.json",
            headers={"X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN},
            json={"product": {
                "title": p["name"],
                "body_html": p.get("notes") or "",
                "status": "draft",
                "tags": p.get("niche") or "",
            }},
        )

    if res.status_code == 201:
        draft = res.json()["product"]
        store_name = shop.replace(".myshopify.com", "")
        return {
            "shopify_id": draft["id"],
            "url": f"https://admin.shopify.com/store/{store_name}/products/{draft['id']}",
            "title": draft["title"],
        }
    return {"error": f"Shopify error ({res.status_code}) — check your access token"}


@router.get("/briefing")
async def get_briefing():
    """Return today's briefing data as structured JSON."""
    import asyncio
    from datetime import datetime
    from tgbot.briefing import get_orders_summary, get_recent_research, get_recent_tasks, get_max_tip

    orders, research, tasks = await asyncio.gather(
        get_orders_summary(),
        get_recent_research(),
        get_recent_tasks(),
    )

    completed = [t for t in tasks if t["status"] == "complete"]
    failed = [t for t in tasks if t["status"] == "failed"]
    context = (
        f"Orders: {orders}. Research topics: {[r['topic'] for r in research]}. "
        f"Tasks: {len(completed)} complete, {len(failed)} failed."
    )
    tip = await get_max_tip(context)

    return {
        "date": datetime.now().strftime("%A, %d %b %Y"),
        "orders": orders,
        "research": research,
        "tasks": {"completed": len(completed), "failed": len(failed)},
        "tip": tip,
    }


@router.get("/tasks")
async def get_tasks(status: str = None, limit: int = 50):
    """Get agent task history."""
    from database.client import supabase
    query = supabase.table("agent_tasks").select("*").order(
        "created_at", desc=True
    ).limit(limit)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data

# api/dashboard.py
# Endpoints that power the web dashboard.

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from typing import Literal, Optional

from api.rate_limit import limiter

router = APIRouter()

# Matches frontend/app.js's VALID_STATUSES -- previously only clamped
# client-side, with no equivalent enforcement here.
ProductStatus = Literal["idea", "researching", "testing", "active", "dropped"]
TaskStatus = Literal["pending", "running", "complete", "failed"]


class ProductCreate(BaseModel):
    name: str
    niche: Optional[str] = None
    score: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


class StatusUpdate(BaseModel):
    status: ProductStatus


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    score: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None
    cost_estimate: Optional[float] = Field(default=None, ge=0)
    sell_price_estimate: Optional[float] = Field(default=None, ge=0)
    margin_estimate: Optional[float] = None


@router.get("/summary")
async def get_dashboard_summary():
    """
    Returns a summary of everything for the dashboard home page.
    Product ideas, recent research, agent activity, task status.
    """
    from database.client import supabase

    # Recent research (display only, keep small)
    research = await supabase.table("research").select("*").order(
        "created_at", desc=True
    ).limit(5).execute()

    # Recent agent tasks (display only)
    tasks = await supabase.table("agent_tasks").select("*").order(
        "created_at", desc=True
    ).limit(10).execute()

    # Products — fetch up to 200 so status breakdown and stat count are accurate
    products = await supabase.table("products").select("*").order(
        "created_at", desc=True
    ).limit(200).execute()

    # Total counts for accurate dashboard stats
    try:
        research_count = await supabase.table("research").select("id", count="exact").execute()
        tasks_count = await supabase.table("agent_tasks").select("id", count="exact").execute()
        total_research = research_count.count or len(research.data)
        total_tasks = tasks_count.count or len(tasks.data)
    except Exception:
        total_research = len(research.data)
        total_tasks = len(tasks.data)

    return {
        "recent_research": research.data,
        "recent_tasks": tasks.data,
        "products": products.data,
        "total_products": len(products.data),
        "total_research": total_research,
        "total_tasks": total_tasks,
    }


@router.get("/products")
async def get_products(status: Optional[ProductStatus] = None):
    """Get all products, optionally filtered by status."""
    from database.client import supabase
    query = supabase.table("products").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = await query.execute()
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
    fields = body.dict(exclude_unset=True)
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
@limiter.limit("20/hour")
async def create_shopify_draft(request: Request, product_id: str):
    """Propose pushing a product to Shopify as a draft listing -- creates an
    `actions` row and sends a Telegram Approve/Reject request; nothing is
    actually created on Shopify until you approve it (see
    tgbot/approvals.py's ACTION_EXECUTORS, which do the real Shopify call)."""
    import config
    from database.client import supabase, create_action
    from tgbot.approvals import send_approval_request

    if not config.SHOPIFY_ACCESS_TOKEN or not config.SHOPIFY_SHOP_URL:
        return {"error": "Shopify not configured — add SHOPIFY_ACCESS_TOKEN and SHOPIFY_STORE_URL to .env"}

    result = await supabase.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")

    p = result.data[0]

    try:
        action = await create_action(
            type="create_shopify_product",
            proposing_agent="dashboard",
            payload={
                "title": p["name"],
                "body_html": p.get("notes") or "",
                "status": "draft",
                "tags": p.get("niche") or "",
            },
            idempotency_key=f"create_shopify_product:dashboard:{product_id}",
        )
    except Exception as e:
        # Most likely an idempotency_key collision -- this product already
        # has a pending proposal awaiting a decision.
        return {"error": f"Could not propose draft (already pending approval?): {e}"}

    if action.get("id"):
        await send_approval_request(action)

    return {"status": "proposed", "action_id": action.get("id")}


@router.get("/briefing")
@limiter.limit("10/hour")
async def get_briefing(request: Request):
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


@router.get("/revenue")
@limiter.limit("30/hour")
async def get_revenue(request: Request, days: int = Query(default=30, ge=1, le=365)):
    """Daily revenue from Shopify for the last N days."""
    import config
    from datetime import datetime, timedelta
    from collections import defaultdict
    from tools.shopify_tools import get_orders

    if not config.SHOPIFY_ACCESS_TOKEN or not config.SHOPIFY_SHOP_URL:
        return []

    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        orders = await get_orders(status="any", limit=250, created_at_min=since)
    except Exception:
        return []

    daily = defaultdict(float)
    for o in orders:
        if o.get("financial_status") in ("paid", "partially_paid"):
            daily[o["created_at"][:10]] += float(o.get("total_price") or 0)

    return [
        {"date": (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d"),
         "revenue": round(daily.get(
             (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d"), 0), 2)}
        for i in range(days)
    ]


@router.get("/tasks")
async def get_tasks(status: Optional[TaskStatus] = None, limit: int = Query(default=50, ge=1, le=500)):
    """Get agent task history."""
    from database.client import supabase
    query = supabase.table("agent_tasks").select("*").order(
        "created_at", desc=True
    ).limit(limit)
    if status:
        query = query.eq("status", status)
    result = await query.execute()
    return result.data

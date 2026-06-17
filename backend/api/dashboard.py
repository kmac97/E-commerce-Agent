# api/dashboard.py
# Endpoints that power the web dashboard.

from fastapi import APIRouter

router = APIRouter()


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

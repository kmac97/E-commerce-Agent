# database/client.py
# Supabase connection and all database operations.

import logging
from typing import Optional
from supabase import create_client, Client

import config

logger = logging.getLogger(__name__)

# Global Supabase client
supabase: Client = None


async def init_db():
    """Initialise the Supabase connection at startup."""
    global supabase
    supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    logger.info("✅ Supabase client initialised")


# ─────────────────────────────────────────
# AGENT TASKS
# ─────────────────────────────────────────

async def save_task_log(
    task_id: str,
    agent: str,
    task: str,
    status: str = "pending",
    input: dict = None,
) -> dict:
    """Log the start of an agent task."""
    data = {
        "id": task_id,
        "agent": agent,
        "task": task,
        "status": status,
        "input": input or {},
    }
    result = supabase.table("agent_tasks").insert(data).execute()
    return result.data[0] if result.data else {}


async def update_task_log(
    task_id: str,
    status: str,
    output: dict = None,
    error: str = None,
    duration_seconds: int = None,
):
    """Update an existing agent task log."""
    updates = {"status": status}
    if output:
        updates["output"] = output
    if error:
        updates["error"] = error
    if duration_seconds:
        updates["duration_seconds"] = duration_seconds

    supabase.table("agent_tasks").update(updates).eq("id", task_id).execute()


async def get_task(task_id: str) -> Optional[dict]:
    """Get a single task by ID."""
    result = supabase.table("agent_tasks").select("*").eq("id", task_id).execute()
    return result.data[0] if result.data else None


# ─────────────────────────────────────────
# RESEARCH
# ─────────────────────────────────────────

async def save_research(
    type: str,
    topic: str,
    data: dict,
    score: int = None,
    notes: str = None,
) -> dict:
    """Save research results to Supabase."""
    record = {
        "type": type,
        "topic": topic,
        "data": data,
    }
    if score is not None:
        record["score"] = score
    if notes:
        record["notes"] = notes

    result = supabase.table("research").insert(record).execute()
    return result.data[0] if result.data else {}


async def get_research(type: str = None, limit: int = 20) -> list:
    """Get saved research, optionally filtered by type."""
    query = supabase.table("research").select("*").order("created_at", desc=True).limit(limit)
    if type:
        query = query.eq("type", type)
    result = query.execute()
    return result.data


async def get_research_by_id(research_id: str) -> Optional[dict]:
    """Get a single research item by ID."""
    result = supabase.table("research").select("*").eq("id", research_id).execute()
    return result.data[0] if result.data else None


async def update_research_fields(research_id: str, fields: dict):
    """Update arbitrary research fields (score, notes, etc)."""
    supabase.table("research").update(fields).eq("id", research_id).execute()


async def delete_research(research_id: str):
    """Delete a research item."""
    supabase.table("research").delete().eq("id", research_id).execute()


# ─────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────

async def save_product(
    name: str,
    niche: str = None,
    score: int = None,
    cost_estimate: float = None,
    sell_price_estimate: float = None,
    margin_estimate: float = None,
    notes: str = None,
    data: dict = None,
) -> dict:
    """Save a product idea to the pipeline."""
    record = {"name": name, "status": "idea"}
    if niche:
        record["niche"] = niche
    if score is not None:
        record["score"] = score
    if cost_estimate is not None:
        record["cost_estimate"] = cost_estimate
    if sell_price_estimate is not None:
        record["sell_price_estimate"] = sell_price_estimate
    if margin_estimate is not None:
        record["margin_estimate"] = margin_estimate
    if notes:
        record["notes"] = notes
    if data:
        record["data"] = data

    result = supabase.table("products").insert(record).execute()
    return result.data[0] if result.data else {}


async def update_product_status(product_id: str, status: str):
    """Update a product's status in the pipeline."""
    supabase.table("products").update({"status": status}).eq("id", product_id).execute()


async def update_product_fields(product_id: str, fields: dict):
    """Update arbitrary product fields."""
    supabase.table("products").update(fields).eq("id", product_id).execute()


async def delete_product(product_id: str):
    """Delete a product from the pipeline."""
    supabase.table("products").delete().eq("id", product_id).execute()


# ─────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────

async def save_memory(agent: str, content: str, metadata: dict = None):
    """Save something to the agent's long-term memory."""
    record = {
        "agent": agent,
        "content": content,
        "metadata": metadata or {},
    }
    supabase.table("memories").insert(record).execute()

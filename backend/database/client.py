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


# ─────────────────────────────────────────
# ACTIONS / APPROVALS / AUDIT LOG (Phase 1 approval gate)
# ─────────────────────────────────────────

async def _append_audit_log(action_id: str, event: str, detail: dict = None):
    """Append-only lifecycle entry for an action. Internal -- called by the
    functions below, never directly, so every action state change is always
    accompanied by a trail entry."""
    record = {"action_id": action_id, "event": event}
    if detail is not None:
        record["detail"] = detail
    supabase.table("audit_log").insert(record).execute()


async def get_action_by_idempotency_key(idempotency_key: str) -> Optional[dict]:
    """Look up an existing action before proposing a duplicate (e.g. the same
    research topic scoring 7+ twice shouldn't create two draft proposals)."""
    result = supabase.table("actions").select("*").eq("idempotency_key", idempotency_key).execute()
    return result.data[0] if result.data else None


async def create_action(
    type: str,
    proposing_agent: str,
    payload: dict,
    before: dict = None,
    risk_level: str = "low",
    idempotency_key: str = None,
) -> dict:
    """Propose a new action awaiting approval. Status defaults to 'proposed'."""
    record = {
        "type": type,
        "proposing_agent": proposing_agent,
        "payload": payload,
        "risk_level": risk_level,
    }
    if before is not None:
        record["before"] = before
    if idempotency_key:
        record["idempotency_key"] = idempotency_key

    result = supabase.table("actions").insert(record).execute()
    action = result.data[0] if result.data else {}
    if action.get("id"):
        await _append_audit_log(action["id"], "proposed", {"payload": payload})
    return action


async def get_action(action_id: str) -> Optional[dict]:
    """Get a single action by ID."""
    result = supabase.table("actions").select("*").eq("id", action_id).execute()
    return result.data[0] if result.data else None


async def record_approval(
    action_id: str,
    decision: str,
    reason: str = None,
    decided_by: str = None,
) -> dict:
    """Record an approve/reject decision, update the action's status to match,
    and audit-log it. decision must be 'approved' or 'rejected'."""
    approval_record = {"action_id": action_id, "decision": decision}
    if reason:
        approval_record["reason"] = reason
    if decided_by:
        approval_record["decided_by"] = decided_by

    result = supabase.table("approvals").insert(approval_record).execute()
    approval = result.data[0] if result.data else {}

    supabase.table("actions").update({"status": decision}).eq("id", action_id).execute()
    await _append_audit_log(action_id, decision, {"reason": reason} if reason else None)
    return approval


async def mark_action_executed(action_id: str, result: dict = None):
    """Mark an approved action as executed, storing its result, and audit-log it."""
    updates = {"status": "executed"}
    if result is not None:
        updates["result"] = result
    supabase.table("actions").update(updates).eq("id", action_id).execute()
    await _append_audit_log(action_id, "executed", result)


async def mark_action_failed(action_id: str, error: str):
    """Mark an action as failed (e.g. execution errored after approval), storing
    the error, and audit-log it."""
    supabase.table("actions").update({"status": "failed", "error": error}).eq("id", action_id).execute()
    await _append_audit_log(action_id, "failed", {"error": error})

# api/research.py
# Endpoints for viewing saved research from Supabase.

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ResearchUpdate(BaseModel):
    score: Optional[int] = None
    notes: Optional[str] = None


@router.get("/")
async def list_research(
    type: str = Query(None, description="Filter by type: product, niche, competitor"),
    limit: int = Query(20, description="Number of results"),
):
    """List all saved research, optionally filtered by type."""
    from database.client import get_research
    return await get_research(type=type, limit=limit)


@router.get("/{research_id}")
async def get_research_item(research_id: str):
    """Get a single research item by ID."""
    from database.client import get_research_by_id
    item = await get_research_by_id(research_id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Research not found")
    return item


@router.patch("/{research_id}")
async def update_research_item(research_id: str, body: ResearchUpdate):
    """Update research score or notes."""
    from database.client import update_research_fields
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        await update_research_fields(research_id, fields)
    return {"status": "updated"}


@router.delete("/{research_id}")
async def delete_research_item(research_id: str):
    """Delete a research item."""
    from database.client import delete_research
    await delete_research(research_id)
    return {"status": "deleted"}

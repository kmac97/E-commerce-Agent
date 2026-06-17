# api/agents.py
# Endpoints to trigger agents from the web dashboard or external calls.

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from agents.crew import run_research_task

router = APIRouter()


class ResearchRequest(BaseModel):
    topic: str
    type: str = "product"  # product, niche, competitor


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/research", response_model=TaskResponse)
async def trigger_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Trigger the research agent to investigate a product or niche.
    Runs in the background — results saved to Supabase and sent via Telegram.
    """
    import uuid
    task_id = str(uuid.uuid4())

    background_tasks.add_task(
        run_research_task,
        task_id=task_id,
        topic=request.topic,
        research_type=request.type,
    )

    return TaskResponse(
        task_id=task_id,
        status="started",
        message=f"Research started for '{request.topic}'. You'll get a Telegram notification when done.",
    )


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Check the status of a running agent task."""
    from database.client import get_task
    task = await get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

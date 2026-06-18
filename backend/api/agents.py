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


class ChatRequest(BaseModel):
    message: str
    history: list = []


@router.post("/chat")
async def chat_with_max(request: ChatRequest):
    """Send a message to Max and get a response."""
    import httpx
    import config as cfg
    from tgbot.commands import SYSTEM_PROMPT

    realtime_triggers = [
        "trend", "trending", "selling", "hot right now", "right now",
        "currently", "today", "this week", "winning product", "best product",
        "niche", "market", "demand", "popular", "viral", "opportunity",
    ]
    needs_realtime = any(t in request.message.lower() for t in realtime_triggers)

    system = SYSTEM_PROMPT
    if needs_realtime and cfg.TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": cfg.TAVILY_API_KEY, "query": request.message,
                          "search_depth": "basic", "max_results": 3, "include_answer": True},
                )
                d = r.json()
                snippets = []
                if d.get("answer"):
                    snippets.append(d["answer"])
                for result in d.get("results", [])[:2]:
                    snippets.append(f"- {result.get('title', '')}: {result.get('content', '')[:200]}")
                if snippets:
                    system += "\n\nLIVE WEB DATA:\n" + "\n".join(snippets)
        except Exception:
            pass

    messages = [{"role": "system", "content": system}]
    messages += request.history[-20:]
    messages.append({"role": "user", "content": request.message})

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": cfg.OPENROUTER_MODEL, "messages": messages, "max_tokens": 500, "temperature": 0.85},
        )
        data = res.json()
        reply = data["choices"][0]["message"]["content"].strip()

    return {"reply": reply}

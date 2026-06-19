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


@router.post("/import-product")
async def import_product_from_url(body: dict):
    """Fetch a product URL and extract structured product data using AI."""
    import httpx, json, re
    import config as cfg

    url = body.get("url", "").strip()
    if not url:
        return {"error": "URL required"}

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0"}) as client:
            res = await client.get(url)
        # Strip tags for a clean text payload
        text = re.sub(r"<[^>]+>", " ", res.text)
        text = re.sub(r"\s+", " ", text).strip()[:3500]
    except Exception as e:
        return {"error": f"Could not fetch URL: {e}"}

    prompt = (
        'Extract product details from this page. Return ONLY valid JSON with exactly these keys:\n'
        '{"name":"product name","niche":"category or niche","cost_estimate":null,"notes":"1-2 sentence description"}\n\n'
        f'Page text: {text}'
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{cfg.OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}"},
                json={"model": cfg.OPENROUTER_FAST_MODEL,
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 200, "temperature": 0.2},
            )
        reply = r.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        return json.loads(match.group()) if match else {"error": "Could not parse product details"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/spy-store")
async def spy_competitor_store(url: str):
    """Fetch the public product catalogue of any Shopify store."""
    import httpx, re

    match = re.search(r"([\w-]+\.myshopify\.com)", url)
    domain = match.group(1) if match else url.replace("https://", "").replace("http://", "").split("/")[0]

    try:
        async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "Mozilla/5.0"}) as client:
            res = await client.get(f"https://{domain}/products.json?limit=50")
        if res.status_code != 200:
            return {"error": f"Store returned {res.status_code} — it may be private or password protected"}
        products = res.json().get("products", [])
        return {
            "domain": domain,
            "count": len(products),
            "products": [{
                "title": p["title"],
                "type": p.get("product_type") or "",
                "price": p["variants"][0]["price"] if p.get("variants") else None,
                "published": (p.get("published_at") or "")[:10],
            } for p in products],
        }
    except Exception as e:
        return {"error": str(e)}


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

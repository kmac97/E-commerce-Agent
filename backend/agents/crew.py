# agents/crew.py
# The main orchestrator. Creates the crew and kicks off tasks.

import logging
import re
import json
from datetime import datetime

import httpx
from crewai import Crew, Process

from agents.researcher import create_researcher_agent, create_research_task
from agents.store_manager import create_store_manager_agent
from agents.marketer import create_marketer_agent
from agents.support_agent import create_support_agent
from agents.analyst import create_analyst_agent
from database.client import save_task_log, update_task_log, save_research, create_action
from tgbot.bot import send_telegram_message
import config

logger = logging.getLogger(__name__)


def _extract_score(text: str) -> int:
    """Extract numeric score from research output. Returns 0 if not found."""
    # Match patterns like "7/10", "Score: 8", "8 out of 10", "score: 7/10"
    patterns = [
        r'(\d+)\s*/\s*10',
        r'score[:\s]+(\d+)',
        r'(\d+)\s+out\s+of\s+10',
        r'rating[:\s]+(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if 1 <= score <= 10:
                return score
    return 0


async def _propose_shopify_draft(task_id: str, topic: str, research_text: str) -> dict | None:
    """
    Use the LLM to extract product listing details from research, then propose
    a Shopify draft as an `actions` row awaiting Telegram approval -- does NOT
    write to Shopify directly (see tgbot/approvals.py, which executes it once
    approved). Returns the created action dict, or None if extraction/proposal
    failed. Never raises: a proposal failure must not take down the research
    task that triggered it.
    """
    if not config.SHOPIFY_ACCESS_TOKEN:
        return None

    # Ask the LLM to extract structured product info from the research
    prompt = f"""Extract product listing details from this research report and return ONLY valid JSON.

Research topic: {topic}

Research report:
{research_text[:2000]}

Return this exact JSON structure (no markdown, no explanation):
{{
  "title": "product title for Shopify listing",
  "price": "29.99",
  "description": "2-3 sentence product description for the listing",
  "product_type": "category",
  "tags": "tag1,tag2,tag3"
}}

For price, use the estimated selling price from the research. If unclear, use "29.99"."""

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_FAST_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.2,
                },
            )
            data = res.json()
            raw = data["choices"][0]["message"]["content"].strip()

            # Strip markdown code fences if present
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
            product = json.loads(raw)

        shopify_payload = {
            "title": product.get("title", topic),
            "body_html": product.get("description", ""),
            "product_type": product.get("product_type", ""),
            "tags": product.get("tags", ""),
            "variants": [{"price": product.get("price", "29.99")}],
            "status": "draft",
        }

        from tgbot.approvals import send_approval_request

        action = await create_action(
            type="create_shopify_product",
            proposing_agent="researcher",
            payload=shopify_payload,
            idempotency_key=f"create_shopify_product:{task_id}",
        )
        if action.get("id"):
            await send_approval_request(action)
        return action

    except Exception as e:
        logger.error(f"Failed to propose Shopify draft: {e}")
        return None


async def run_research_task(task_id: str, topic: str, research_type: str = "product"):
    """
    Run a full product/niche research task using the researcher agent.
    Saves results to Supabase and sends a Telegram notification when done.
    """
    start_time = datetime.now()

    # Log task start
    await save_task_log(
        task_id=task_id,
        agent="researcher",
        task=f"Research {research_type}: {topic}",
        status="running",
        input={"topic": topic, "type": research_type},
    )

    await send_telegram_message(f"🔍 Research started: *{topic}*\nI'll notify you when done.")

    try:
        # Create the researcher agent and task
        researcher = create_researcher_agent()
        research_task = create_research_task(researcher, topic, research_type)

        # Run the crew
        crew = Crew(
            agents=[researcher],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True,
        )

        result = await crew.kickoff_async()
        result_text = str(result)

        # Calculate duration
        duration = int((datetime.now() - start_time).total_seconds())

        # Extract score from research output
        score = _extract_score(result_text)

        # Save research to Supabase
        await save_research(
            type=research_type,
            topic=topic,
            data={"raw_output": result_text},
            score=score if score > 0 else None,
        )

        # Update task log
        await update_task_log(
            task_id=task_id,
            status="complete",
            output={"result": result_text, "score": score},
            duration_seconds=duration,
        )

        # Send Telegram notification with summary
        summary = result_text[:800] + "..." if len(result_text) > 800 else result_text
        score_line = f"\n\n📊 *Score: {score}/10*" if score > 0 else ""
        await send_telegram_message(
            f"✅ Research complete: *{topic}*\n\n{summary}{score_line}\n\n"
            f"_Full results saved to dashboard._"
        )

        # Propose a Shopify draft if score is 7 or above -- awaits Telegram approval,
        # does not create it automatically (see _propose_shopify_draft).
        if score >= 7 and research_type == "product":
            await send_telegram_message(
                f"🏪 Score {score}/10 — drafting a Shopify listing proposal for *{topic}*..."
            )
            action = await _propose_shopify_draft(task_id, topic, result_text)
            if not action:
                await send_telegram_message(
                    f"⚠️ Couldn't prepare a Shopify listing proposal — do it manually from the research report."
                )

        logger.info(f"Research task {task_id} completed in {duration}s")

    except Exception as e:
        logger.error(f"Research task {task_id} failed: {e}")

        await update_task_log(
            task_id=task_id,
            status="failed",
            error=str(e),
        )

        await send_telegram_message(
            f"❌ Research failed for *{topic}*\n\nError: {str(e)[:200]}"
        )


def build_full_crew():
    """
    Build the full crew with all agents.
    Used for complex multi-agent tasks in later phases.
    """
    return Crew(
        agents=[
            create_researcher_agent(),
            create_store_manager_agent(),
            create_marketer_agent(),
            create_support_agent(),
            create_analyst_agent(),
        ],
        process=Process.hierarchical,
        verbose=True,
    )


# Registers this as the handler for 'research_task' jobs on the durable
# queue (agents/job_worker.py) -- runs at import time, so main.py's startup
# just needs to import this module before starting the worker loop.
from agents.job_worker import register_job_handler  # noqa: E402
register_job_handler("research_task", run_research_task)

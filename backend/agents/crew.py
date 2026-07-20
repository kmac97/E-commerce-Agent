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
from database.client import save_task_log, update_task_log, save_research
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


async def _auto_create_shopify_draft(topic: str, research_text: str) -> str | None:
    """
    Use GPT to extract product details from research, then create a Shopify draft.
    Returns the Shopify admin URL on success, None on failure.
    """
    if not config.SHOPIFY_ACCESS_TOKEN:
        return None

    # Ask GPT to extract structured product info from the research
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

    except Exception as e:
        logger.error(f"Failed to extract product details: {e}")
        return None

    # Create the Shopify draft
    try:
        from tools.shopify_tools import shopify_url, get_headers
        payload = {
            "product": {
                "title": product.get("title", topic),
                "body_html": product.get("description", ""),
                "product_type": product.get("product_type", ""),
                "tags": product.get("tags", ""),
                "variants": [{"price": product.get("price", "29.99")}],
                "status": "draft",
            }
        }
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                shopify_url("products.json"),
                json=payload,
                headers=get_headers(),
            )
            if res.status_code not in (200, 201):
                logger.error(f"Shopify draft creation failed: {res.status_code} {res.text}")
                return None
            created = res.json().get("product", {})
            product_id = created.get("id")
            if not product_id:
                logger.error("Shopify response missing product id")
                return None
            shop = config.SHOPIFY_SHOP_URL.replace("https://", "").replace("http://", "").rstrip("/")
            return f"https://{shop}/admin/products/{product_id}"

    except Exception as e:
        logger.error(f"Shopify draft creation error: {e}")
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

        # Auto-create Shopify draft if score is 7 or above
        if score >= 7 and research_type == "product":
            await send_telegram_message(
                f"🏪 Score {score}/10 — creating Shopify draft listing for *{topic}*..."
            )
            shopify_url_result = await _auto_create_shopify_draft(topic, result_text)
            if shopify_url_result:
                await send_telegram_message(
                    f"✅ Shopify draft created!\n\n"
                    f"Review and publish it here:\n{shopify_url_result}"
                )
            else:
                await send_telegram_message(
                    f"⚠️ Couldn't auto-create the Shopify listing — do it manually from the research report."
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

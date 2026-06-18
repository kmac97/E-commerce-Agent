# tgbot/briefing.py
# Daily morning briefing sent to Telegram by Max.
# Pulls yesterday's orders, recent research, and agent activity.
# Scheduled via PM2 ecosystem config or a cron job.

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


async def get_orders_summary() -> dict:
    """Fetch yesterday's Shopify orders."""
    if not config.SHOPIFY_ACCESS_TOKEN:
        return None
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                f"https://{config.SHOPIFY_SHOP_URL}/admin/api/{config.SHOPIFY_API_VERSION}"
                f"/orders.json?status=any&created_at_min={yesterday}&limit=250",
                headers={
                    "X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN,
                    "Content-Type": "application/json",
                },
            )
            if res.status_code != 200:
                return None
            orders = res.json().get("orders", [])
            revenue = sum(float(o.get("total_price", 0)) for o in orders)
            return {
                "count": len(orders),
                "revenue": round(revenue, 2),
                "currency": orders[0].get("currency", "USD") if orders else "USD",
            }
    except Exception as e:
        logger.error(f"Orders fetch failed: {e}")
        return None


async def get_recent_research() -> list:
    """Fetch research completed in the last 24 hours from Supabase."""
    try:
        from database.client import supabase
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = (
            supabase.table("research")
            .select("topic, type, score, created_at")
            .gte("created_at", yesterday)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Research fetch failed: {e}")
        return []


async def get_recent_tasks() -> list:
    """Fetch agent tasks from the last 24 hours."""
    try:
        from database.client import supabase
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        result = (
            supabase.table("agent_tasks")
            .select("agent, task, status, duration_seconds")
            .gte("created_at", yesterday)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Tasks fetch failed: {e}")
        return []


async def build_briefing() -> str:
    """Assemble the full daily briefing message."""
    today = datetime.now().strftime("%A, %d %b %Y")

    orders, research, tasks = await asyncio.gather(
        get_orders_summary(),
        get_recent_research(),
        get_recent_tasks(),
    )

    lines = [f"☀️ *Good morning — daily briefing for {today}*\n"]

    # Orders
    lines.append("🛒 *Orders (last 24h)*")
    if orders is None:
        lines.append("_Shopify not connected_")
    elif orders["count"] == 0:
        lines.append("No orders yesterday.")
    else:
        lines.append(f"{orders['count']} orders · ${orders['revenue']} {orders['currency']}")
    lines.append("")

    # Research
    lines.append("🔍 *Research completed*")
    if not research:
        lines.append("Nothing researched yesterday.")
    else:
        for r in research:
            score_str = f" [{r['score']}/10]" if r.get("score") else ""
            lines.append(f"• {r['topic']}{score_str} _{r['type']}_")
    lines.append("")

    # Agent activity
    lines.append("🤖 *Agent activity*")
    complete = [t for t in tasks if t["status"] == "complete"]
    failed = [t for t in tasks if t["status"] == "failed"]
    if not tasks:
        lines.append("No tasks ran yesterday.")
    else:
        lines.append(f"{len(complete)} completed · {len(failed)} failed")
        for t in failed:
            lines.append(f"⚠️ Failed: {t['task'][:60]}")
    lines.append("")

    # Ask Max for a quick tip based on the data
    briefing_context = "\n".join(lines)
    tip = await get_max_tip(briefing_context)
    if tip:
        lines.append(f"💡 *Max says:* {tip}")

    return "\n".join(lines)


async def get_max_tip(context: str) -> str:
    """Ask Max for a one-line insight or action based on today's data."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are Max, a sharp e-commerce business partner. "
                                "Based on this daily briefing data, give ONE short, specific, "
                                "actionable insight or recommendation. "
                                "2 sentences max. No fluff. Be direct."
                            ),
                        },
                        {"role": "user", "content": context},
                    ],
                    "max_tokens": 100,
                    "temperature": 0.8,
                },
            )
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Max tip failed: {e}")
        return ""


async def send_daily_briefing():
    """Build and send the daily briefing to Telegram."""
    logger.info("Sending daily briefing...")

    # Init Supabase (needed when run as standalone script)
    try:
        from database.client import init_db
        await init_db()
    except Exception:
        pass

    briefing = await build_briefing()

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=briefing,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("Daily briefing sent.")
    except Exception as e:
        # Fallback: strip markdown
        logger.warning(f"Markdown send failed: {e}")
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=briefing,
            parse_mode=None,
        )


if __name__ == "__main__":
    # Run directly: python -m tgbot.briefing
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(send_daily_briefing())

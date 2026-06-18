# telegram/commands.py
# Handles all Telegram bot commands and messages.

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sent when user types /start"""
    await update.message.reply_text(
        "👋 *E-commerce AI Agent online.*\n\n"
        "I'm your autonomous business assistant. Here's what I can do:\n\n"
        "🔍 `/research [product/niche]` — Research a product or niche\n"
        "📦 `/products` — View your product pipeline\n"
        "✅ `/tasks` — See recent agent activity\n"
        "📊 `/status` — System status\n"
        "❓ `/help` — Full command list\n\n"
        "Or just type naturally and I'll help you out.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full command list"""
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "*Research*\n"
        "`/research posture correctors` — Full product research\n"
        "`/research niche: pet accessories` — Niche research\n"
        "`/research competitor: gymshark` — Competitor analysis\n\n"
        "*Store* _(Phase 3)_\n"
        "`/orders` — Today's orders\n"
        "`/inventory` — Low stock alerts\n\n"
        "*Marketing* _(Phase 4)_\n"
        "`/ads` — Campaign performance\n"
        "`/hooks [product]` — Generate ad hooks\n\n"
        "*Support* _(Phase 5)_\n"
        "`/reviews` — Latest reviews\n"
        "`/emails` — Unread customer emails\n\n"
        "*System*\n"
        "`/products` — Product pipeline\n"
        "`/tasks` — Agent task history\n"
        "`/status` — System health\n",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_research(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger a research task: /research [topic]"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a topic.\n\nExamples:\n"
            "`/research posture correctors`\n"
            "`/research niche: pet accessories`\n"
            "`/research competitor: gymshark`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    raw = " ".join(context.args)

    # Detect research type from prefix
    if raw.lower().startswith("niche:"):
        topic = raw[6:].strip()
        research_type = "niche"
    elif raw.lower().startswith("competitor:"):
        topic = raw[11:].strip()
        research_type = "competitor"
    else:
        topic = raw
        research_type = "product"

    await update.message.reply_text(
        f"🔍 Starting {research_type} research: *{topic}*\n\nI'll notify you when done.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Kick off the agent task
    import uuid
    from agents.crew import run_research_task
    import asyncio

    task_id = str(uuid.uuid4())
    asyncio.create_task(
        run_research_task(task_id=task_id, topic=topic, research_type=research_type)
    )


async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent Shopify orders"""
    import config as cfg
    if not cfg.SHOPIFY_ACCESS_TOKEN:
        await update.message.reply_text("Shopify not connected yet.")
        return
    try:
        from tools.shopify_tools import get_orders_summary
        summary = await get_orders_summary()
        await update.message.reply_text(
            f"🛒 *Store Orders*\n\n"
            f"Total orders: {summary['total_orders']}\n"
            f"Total revenue: ${summary['total_revenue']} {summary['currency']}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"Error fetching orders: {str(e)[:200]}")


async def cmd_store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show store product listings"""
    import config as cfg
    if not cfg.SHOPIFY_ACCESS_TOKEN:
        await update.message.reply_text("Shopify not connected yet.")
        return
    try:
        from tools.shopify_tools import get_products
        products = await get_products(limit=10)
        if not products:
            await update.message.reply_text("No products in your store yet.")
            return
        lines = [f"🏪 *Shopify Store* ({len(products)} products)\n"]
        for p in products:
            price = p.get("variants", [{}])[0].get("price", "?")
            status = "✅" if p["status"] == "active" else "📝"
            lines.append(f"{status} {p['title']} — ${price}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Error fetching store: {str(e)[:200]}")


async def cmd_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the product pipeline"""
    from database.client import supabase

    result = supabase.table("products").select("name, status, score").order(
        "created_at", desc=True
    ).limit(10).execute()

    if not result.data:
        await update.message.reply_text("No products saved yet. Try `/research [product]` first.")
        return

    lines = ["📦 *Product Pipeline*\n"]
    status_emoji = {
        "idea": "💡", "researching": "🔍", "testing": "🧪",
        "active": "✅", "dropped": "❌"
    }
    for p in result.data:
        emoji = status_emoji.get(p.get("status", "idea"), "•")
        score = f" [{p['score']}/10]" if p.get("score") else ""
        lines.append(f"{emoji} {p['name']}{score} — _{p.get('status', 'idea')}_")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent agent tasks"""
    from database.client import supabase

    result = supabase.table("agent_tasks").select(
        "agent, task, status, created_at"
    ).order("created_at", desc=True).limit(8).execute()

    if not result.data:
        await update.message.reply_text("No agent tasks yet.")
        return

    lines = ["🤖 *Recent Agent Activity*\n"]
    status_emoji = {"pending": "⏳", "running": "🔄", "complete": "✅", "failed": "❌"}
    for t in result.data:
        emoji = status_emoji.get(t.get("status", "pending"), "•")
        date = t["created_at"][:10] if t.get("created_at") else ""
        lines.append(f"{emoji} [{t['agent']}] {t['task'][:50]} _{date}_")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System health check"""
    import config as cfg

    checks = {
        "OpenRouter": bool(cfg.OPENROUTER_API_KEY),
        "Supabase": bool(cfg.SUPABASE_URL and cfg.SUPABASE_KEY),
        "Tavily Search": bool(cfg.TAVILY_API_KEY),
        "Shopify": bool(cfg.SHOPIFY_ACCESS_TOKEN),
        "Meta Ads": bool(cfg.META_ACCESS_TOKEN),
        "Gmail": bool(cfg.GMAIL_CLIENT_ID),
    }

    lines = ["📊 *System Status*\n"]
    for service, connected in checks.items():
        emoji = "✅" if connected else "⚠️"
        status = "connected" if connected else "not configured"
        lines.append(f"{emoji} {service} — _{status}_")

    lines.append(f"\n🧠 Model: `{cfg.OPENROUTER_MODEL}`")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle plain text messages.
    Only triggers research if the message looks like a product/niche query.
    Otherwise responds with help text.
    """
    text = update.message.text.strip().lower()

    # Keywords that suggest a research request
    research_triggers = [
        "research", "find", "look up", "analyse", "analyze", "niche",
        "product", "sell", "dropship", "trending", "winning", "competitor",
        "how is", "what about", "tell me about",
    ]

    is_research = any(trigger in text for trigger in research_triggers)

    if is_research:
        await update.message.reply_text(
            f"🔍 Researching: *{update.message.text[:100]}*\n\nI'll notify you when done.",
            parse_mode=ParseMode.MARKDOWN,
        )
        import uuid
        from agents.crew import run_research_task
        import asyncio
        task_id = str(uuid.uuid4())
        asyncio.create_task(
            run_research_task(task_id=task_id, topic=update.message.text, research_type="product")
        )
    else:
        await update.message.reply_text(
            "Here's what I can do:\n\n"
            "/research [product] — Research a product\n"
            "/store — View Shopify listings\n"
            "/orders — Check orders\n"
            "/products — Product pipeline\n"
            "/tasks — Recent agent activity\n"
            "/status — System health\n\n"
            "Or type: research posture correctors",
        )

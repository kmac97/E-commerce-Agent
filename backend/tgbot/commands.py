# tgbot/commands.py
# Handles all Telegram bot commands and messages.

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# In-memory conversation history (per chat session)
_conversation_history: dict[int, list] = {}

SYSTEM_PROMPT = """You are Max — a sharp, experienced e-commerce business partner and operator.
You're not a chatbot or assistant. You're a co-founder who has built and scaled multiple Shopify stores.
You speak directly, confidently, and practically. No fluff, no corporate speak.

Your personality:
- Straight-talking but friendly — like a business partner texting you
- You know your stuff: product research, dropshipping, paid ads, Shopify, margins, ROAS
- You give real opinions. If an idea is bad, say so and why. If it's good, get excited about it
- You use casual language, short sentences, occasional humour
- You remember context from earlier in the conversation
- You never say "As an AI" or "I'm just a bot" — you're Max, a business partner

Your capabilities (what you can actually do):
- Research products and niches using real web data
- Create and manage Shopify product listings
- Monitor orders and store performance
- Eventually: run ads, handle emails, manage reviews

When someone asks you to research something, confirm and kick it off.
When someone's just chatting or asking for advice, respond naturally as Max.
Keep responses concise — this is Telegram, not an essay."""


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
    Handle plain text messages with personality and memory.
    Uses GPT-4o-mini directly for natural conversation.
    Detects research intent and kicks off agent tasks automatically.
    """
    import httpx
    import uuid
    import asyncio
    import config as cfg

    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Initialise conversation history for this chat
    if chat_id not in _conversation_history:
        _conversation_history[chat_id] = []

    # Add user message to history
    _conversation_history[chat_id].append({"role": "user", "content": text})

    # Keep last 20 messages to avoid token overflow
    history = _conversation_history[chat_id][-20:]

    # Detect if the question needs real-time data
    realtime_triggers = [
        "trend", "trending", "selling", "sell now", "hot right now", "what's hot",
        "right now", "currently", "today", "this week", "this month", "2024", "2025", "2026",
        "winning product", "best product", "top product", "what should i", "niche",
        "market", "demand", "popular", "viral", "tiktok", "ads", "opportunity",
    ]
    needs_realtime = any(t in text.lower() for t in realtime_triggers)

    # If real-time data needed, do a quick Tavily search and inject results
    live_context = ""
    if needs_realtime and cfg.TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                tavily_res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": cfg.TAVILY_API_KEY,
                        "query": text,
                        "search_depth": "basic",
                        "max_results": 4,
                        "include_answer": True,
                    },
                )
                tavily_data = tavily_res.json()
                snippets = []
                if tavily_data.get("answer"):
                    snippets.append(tavily_data["answer"])
                for r in tavily_data.get("results", [])[:3]:
                    snippets.append(f"- {r.get('title', '')}: {r.get('content', '')[:200]}")
                if snippets:
                    live_context = "LIVE WEB DATA (use this to answer, today's date is 2026):\n" + "\n".join(snippets)
        except Exception as e:
            logger.warning(f"Tavily quick search failed: {e}")

    # Build messages for the LLM
    system = SYSTEM_PROMPT
    if live_context:
        system = SYSTEM_PROMPT + f"\n\n{live_context}"

    messages = [{"role": "system", "content": system}] + history

    # Call OpenRouter directly (faster than CrewAI for chat)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg.OPENROUTER_MODEL,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.85,
                },
            )
            data = res.json()
            reply = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Chat LLM error: {e}")
        reply = "Something went wrong on my end — try again in a sec."

    # Save assistant reply to history
    _conversation_history[chat_id].append({"role": "assistant", "content": reply})

    # Detect if Max decided to kick off research
    research_triggers = [
        "researching", "looking into", "on it", "let me research",
        "i'll check", "checking", "running research", "looking that up",
    ]
    lower_reply = reply.lower()
    should_research = any(t in lower_reply for t in research_triggers)

    # Also detect explicit research intent in user message
    user_triggers = ["research ", "look up ", "find me ", "analyse ", "analyze "]
    if any(text.lower().startswith(t) for t in user_triggers):
        should_research = True

    await update.message.reply_text(reply)

    # Kick off research task if needed
    if should_research:
        topic = text
        for prefix in ["research ", "look up ", "find me ", "analyse ", "analyze "]:
            if topic.lower().startswith(prefix):
                topic = topic[len(prefix):]
                break

        task_id = str(uuid.uuid4())
        asyncio.create_task(
            run_research_task_from_chat(task_id=task_id, topic=topic, chat_id=chat_id)
        )


async def run_research_task_from_chat(task_id: str, topic: str, chat_id: int):
    """Wrapper to run research and send result back to the right chat."""
    from agents.crew import run_research_task
    await run_research_task(task_id=task_id, topic=topic, research_type="product")

# tgbot/commands.py
# Handles all Telegram bot commands and messages.

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tgbot.auth import owner_only

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

Your capabilities:
- You have LIVE internet access — you can see what's trending right now, today's prices, current ad spend, real supplier costs. Use this confidently. Never say your info might be outdated.
- Research products and niches with real-time web data
- Create and manage Shopify product listings
- Monitor orders and store performance
- Analyse pipelines, score products, spot market opportunities

When giving product advice, be specific: name real products, give real price ranges, cite where you saw them trending.
When someone asks what's hot right now — answer with confidence, you have live data.
Keep responses concise — punchy and direct, not essays."""


@owner_only
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


@owner_only
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


@owner_only
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

    # Queue the research job (see agents/job_worker.py) -- durable, survives
    # a process restart, unlike asyncio.create_task.
    import uuid
    from database.client import enqueue_job

    task_id = str(uuid.uuid4())
    await enqueue_job(
        type="research_task",
        payload={"task_id": task_id, "topic": topic, "research_type": research_type},
    )


@owner_only
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


@owner_only
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


@owner_only
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


@owner_only
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


@owner_only
async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find trending products right now."""
    await update.message.reply_text(
        "🔍 Scanning for trending products across TikTok, Shopify and Meta... give me ~30 seconds.",
    )
    try:
        from agents.trending import find_trending_products
        report = await find_trending_products()
        try:
            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(report, parse_mode=None)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:200]}")


@owner_only
async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check for low stock items."""
    await update.message.reply_text("🔍 Checking inventory...")
    try:
        from tgbot.store_monitor import check_low_stock
        msg = await check_low_stock(threshold=10)
        if msg:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("✅ All products have healthy stock levels (10+ units).")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:200]}")


@owner_only
async def cmd_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get price monitoring suggestions."""
    await update.message.reply_text("💰 Checking competitor prices, give me a moment...")
    try:
        from tgbot.store_monitor import get_price_suggestions
        msg = await get_price_suggestions()
        if msg:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No active products to check, or Tavily not configured.")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:200]}")


@owner_only
async def cmd_optimise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Optimise a product listing: /optimise [product_id]"""
    if not context.args:
        # No ID given — show list of products to choose from
        try:
            import config as cfg
            if not cfg.SHOPIFY_ACCESS_TOKEN:
                await update.message.reply_text("Shopify not connected.")
                return
            from tools.shopify_tools import get_products
            products = await get_products(limit=20)
            if not products:
                await update.message.reply_text("No products in your store.")
                return
            lines = ["📝 *Choose a product to optimise:*\n"]
            for p in products:
                lines.append(f"`/optimise {p['id']}` — {p['title']}")
            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)[:200]}")
        return

    product_id = context.args[0]
    await update.message.reply_text(f"✍️ Optimising listing {product_id}...")
    try:
        from tgbot.store_monitor import optimise_product_listing
        result = await optimise_product_listing(product_id)
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:200]}")


@owner_only
async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger the daily briefing on demand."""
    await update.message.reply_text("📊 Generating your briefing...")
    try:
        from tgbot.briefing import build_briefing
        briefing = await build_briefing()
        await update.message.reply_text(briefing, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Error generating briefing: {str(e)[:200]}")


@owner_only
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


@owner_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle plain text messages with personality and memory.
    Uses GPT-4o-mini directly for natural conversation.
    Detects research intent and kicks off agent tasks automatically.
    """
    import httpx
    import uuid
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

    from datetime import datetime
    today = datetime.utcnow().strftime("%A, %d %B %Y")
    system = SYSTEM_PROMPT + f"\n\nToday's date: {today}."

    # Perplexity/online models have built-in live search — skip Tavily to avoid conflicts
    is_online_model = "perplexity" in cfg.OPENROUTER_MODEL or "sonar" in cfg.OPENROUTER_MODEL

    if not is_online_model and cfg.TAVILY_API_KEY:
        skip_search = ["hello", "hi ", "hey ", "thanks", "thank you", "bye", "how are you"]
        needs_realtime = not any(t in text.lower() for t in skip_search)
        if needs_realtime:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    tavily_res = await client.post(
                        "https://api.tavily.com/search",
                        json={"api_key": cfg.TAVILY_API_KEY, "query": text,
                              "search_depth": "advanced", "max_results": 5, "include_answer": True},
                    )
                    tavily_data = tavily_res.json()
                    snippets = []
                    if tavily_data.get("answer"):
                        snippets.append(tavily_data["answer"])
                    for r in tavily_data.get("results", [])[:4]:
                        snippets.append(f"- {r.get('title', '')}: {r.get('content', '')[:300]}")
                    if snippets:
                        system += "\n\nLIVE WEB DATA (use this, it is current):\n" + "\n".join(snippets)
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

    messages = [{"role": "system", "content": system}] + history

    # Call the LLM directly (faster than CrewAI for chat)
    from tools.llm_client import call_llm, LLMCallError
    import re as _re
    try:
        raw_reply = await call_llm(
            messages=messages, model=cfg.OPENROUTER_MODEL, max_tokens=500, temperature=0.85, timeout=30,
        )
        reply = _re.sub(r'\[\d+\]', '', raw_reply).strip()
    except LLMCallError as e:
        logger.error(f"Chat LLM error: {e}")
        reply = "Something went wrong on my end — try again in a sec."

    # Save assistant reply to history
    _conversation_history[chat_id].append({"role": "assistant", "content": reply})

    # Detect if Max explicitly committed to running a research task
    # Narrow triggers only — avoids firing on casual "I'm looking into that" replies
    research_triggers = [
        "i'll research that", "let me research that", "researching that for you",
        "running research on", "kicking off research", "starting research on",
    ]
    lower_reply = reply.lower()
    should_research = any(t in lower_reply for t in research_triggers)

    # Also detect explicit research command from user
    user_triggers = ["research ", "analyse ", "analyze "]
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
        await run_research_task_from_chat(task_id=task_id, topic=topic, chat_id=chat_id)


async def run_research_task_from_chat(task_id: str, topic: str, chat_id: int):
    """Queue a research job (see agents/job_worker.py). chat_id is accepted
    for call-site compatibility but unused -- results always go to
    config.TELEGRAM_CHAT_ID, the only chat this bot ever notifies."""
    from database.client import enqueue_job
    await enqueue_job(
        type="research_task",
        payload={"task_id": task_id, "topic": topic, "research_type": "product"},
    )

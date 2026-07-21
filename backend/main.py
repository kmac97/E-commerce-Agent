"""
E-commerce AI Agent — Backend Entry Point
==========================================
Run this on your Hostinger VPS:

    python main.py

Or with uvicorn directly:

    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import config
from config import validate_config
from database.client import init_db
from tgbot.bot import start_telegram_bot, stop_telegram_bot
from api.rate_limit import limiter

# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""

    # Startup
    logger.info("🚀 Starting E-commerce AI Agent...")

    # Validate all required env vars are present
    validate_config()

    # Connect to Supabase
    await init_db()
    logger.info("✅ Supabase connected")

    # Start Telegram bot in background
    bot_task = asyncio.create_task(start_telegram_bot())
    logger.info("✅ Telegram bot started")

    # Start the durable job worker (imports agents.crew first so its
    # research_task handler is registered before the loop starts polling)
    import agents.crew  # noqa: F401
    from agents.job_worker import run_worker_loop
    worker_task = asyncio.create_task(run_worker_loop())
    logger.info("✅ Job worker started")

    logger.info(f"✅ FastAPI running on http://{config.API_HOST}:{config.API_PORT}")
    logger.info(f"✅ Model: {config.OPENROUTER_MODEL}")

    yield  # App runs here

    # Shutdown -- stop the bot's own polling (start_polling() runs its own
    # internal tasks, separate from bot_task, which already completed right
    # after startup) and cancel the worker's long-running loop, so a PM2
    # restart doesn't leave either running against a torn-down event loop.
    logger.info("👋 Shutting down...")

    await stop_telegram_bot()

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    if not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = FastAPI(
    title="E-commerce AI Agent",
    description="Autonomous AI agent for e-commerce research, store management, marketing, and support.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow requests only from the dashboard's known origins (config.ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,  # no session auth — auth is the X-Api-Key header
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Api-Key"],
)

# Rate limiting on expensive/externally-costed endpoints (see api/agents.py, api/dashboard.py)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

from api import agents, research, dashboard, webhooks  # noqa: E402
from api.auth import require_api_key  # noqa: E402

_auth = [Depends(require_api_key)]

app.include_router(agents.router, prefix="/api/agents", tags=["Agents"], dependencies=_auth)
app.include_router(research.router, prefix="/api/research", tags=["Research"], dependencies=_auth)
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"], dependencies=_auth)
# No X-Api-Key dependency -- Shopify's delivery servers can't send it.
# Authenticated instead via HMAC signature verification inside each route.
app.include_router(webhooks.router, prefix="/webhooks/shopify", tags=["Webhooks"])


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "E-commerce AI Agent",
        "version": "1.0.0",
        "model": config.OPENROUTER_MODEL,
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "telegram_bot": config.TELEGRAM_BOT_USERNAME or None,
    }


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG,
        log_level="info",
    )

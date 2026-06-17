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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from config import validate_config
from database.client import init_db
from tgbot.bot import start_telegram_bot

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
    asyncio.create_task(start_telegram_bot())
    logger.info("✅ Telegram bot started")

    logger.info(f"✅ FastAPI running on http://{config.API_HOST}:{config.API_PORT}")
    logger.info(f"✅ Model: {config.OPENROUTER_MODEL}")

    yield  # App runs here

    # Shutdown
    logger.info("👋 Shutting down...")


# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────

app = FastAPI(
    title="E-commerce AI Agent",
    description="Autonomous AI agent for e-commerce research, store management, marketing, and support.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow requests from your Vercel frontend and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this to your Vercel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

from api import agents, research, dashboard, shopify_auth  # noqa: E402

app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(research.router, prefix="/api/research", tags=["Research"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(shopify_auth.router, tags=["Shopify Auth"])


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
    return {"status": "ok"}


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

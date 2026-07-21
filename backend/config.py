# config.py
# Central settings for the E-commerce AI Agent.
# All configuration lives here — change things here, not buried in other files.

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# AI MODEL (via OpenRouter)
# ─────────────────────────────────────────

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Primary model — Claude Haiku 4.5 via OpenRouter (anthropic/claude-haiku-4.5).
# Reached through the existing OpenRouter integration, not the Anthropic SDK directly --
# no new dependency or endpoint, just a different model string on the same API.
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")

# Fast model for extraction/classification tasks. Same model as above for now --
# Haiku 4.5 already is Anthropic's fast/cheap tier. Kept as a separate knob so a
# heavier model (e.g. Claude Sonnet 5, also available via OpenRouter) can be split
# onto OPENROUTER_MODEL later without touching the extraction call sites.
OPENROUTER_FAST_MODEL = os.getenv("OPENROUTER_FAST_MODEL", "anthropic/claude-haiku-4.5")

# Fallback if the primary model/provider is unavailable (tools/llm_client.py
# tries this after exhausting retries on the primary). Deliberately a
# non-Anthropic model for real redundancy against an Anthropic-specific outage.
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "openai/gpt-5.6-luna")

# Research synthesis only (agents/researcher.py's CrewAI agent) -- a heavier
# model than the OPENROUTER_MODEL default, deliberately scoped to just this
# one low-frequency, high-value task (research is rate-limited to 10/hour)
# rather than the build plan's full recommendation of Sonnet 5 for chat/
# trending/listing-drafts too, to keep the cost increase small and
# predictable. Sonnet 5 is ~2x Haiku 4.5 at intro pricing (through 2026-08-31),
# ~3x after -- see AI_Store_Master_Plan.md's budget section before widening
# this to any other call site.
OPENROUTER_RESEARCH_MODEL = os.getenv("OPENROUTER_RESEARCH_MODEL", "anthropic/claude-sonnet-5")

# Model settings
MAX_TOKENS = 2000
TEMPERATURE = 0.7

# ─────────────────────────────────────────
# CORS
# ─────────────────────────────────────────

# Comma-separated list of origins allowed to call the API. Defaults to the
# dashboard's known Vercel domains (production alias, team alias, git-main
# alias). Add a local dev origin via .env (e.g. http://127.0.0.1:5500) if
# you test the frontend locally.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://e-commerce-agent-mu.vercel.app,"
        "https://e-commerce-agent-brighttoproofingos.vercel.app,"
        "https://e-commerce-agent-git-main-brighttoproofingos.vercel.app",
    ).split(",") if o.strip()
]

# ─────────────────────────────────────────
# API AUTH
# ─────────────────────────────────────────

# Shared secret the dashboard sends as X-Api-Key. Generate with: openssl rand -hex 32
API_KEY = os.getenv("API_KEY")

# ─────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")  # e.g. myagent_bot

# ─────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ─────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Legacy Serper (unused — replaced by Tavily)
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# ─────────────────────────────────────────
# SHOPIFY
# ─────────────────────────────────────────

# Single self-owned store, connected via a custom app's static Admin API
# token (Shopify's recommended pattern for a private, non-distributed app) --
# not OAuth. See Phase 3 build-plan note: a full OAuth install flow is for
# apps installed on OTHER merchants' stores, which doesn't apply here or in
# the planned replication model (each new store gets its own instance/token).
SHOPIFY_SHOP_URL = os.getenv("SHOPIFY_STORE_URL") or os.getenv("SHOPIFY_SHOP_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = "2026-07"

# For verifying Shopify webhook HMAC signatures (api/webhooks.py). This is
# the custom app's "API secret key" shown next to the Admin API access
# token in Shopify admin -- not the access token itself.
SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")

# ─────────────────────────────────────────
# META ADS
# ─────────────────────────────────────────

META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID")

# ─────────────────────────────────────────
# GMAIL
# ─────────────────────────────────────────

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")

# ─────────────────────────────────────────
# SERVER
# ─────────────────────────────────────────

API_HOST = "0.0.0.0"
API_PORT = 8000
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ─────────────────────────────────────────
# VALIDATION
# Checks that critical keys exist at startup.
# ─────────────────────────────────────────

def validate_config():
    """
    Check that all required environment variables are set.
    Prints warnings for missing optional ones.
    """
    required = {
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "API_KEY": API_KEY,
    }

    optional = {
        "TAVILY_API_KEY": TAVILY_API_KEY,
        "SHOPIFY_ACCESS_TOKEN": SHOPIFY_ACCESS_TOKEN,
        "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
        "GMAIL_CLIENT_ID": GMAIL_CLIENT_ID,
    }

    missing_required = [k for k, v in required.items() if not v]
    missing_optional = [k for k, v in optional.items() if not v]

    if missing_required:
        raise EnvironmentError(
            f"\n❌ Missing required environment variables:\n" +
            "\n".join(f"   - {k}" for k in missing_required) +
            "\n\nCheck your .env file. See docs/SETUP.md for help.\n"
        )

    if missing_optional:
        print("⚠️  Optional keys not set (features will be limited):")
        for k in missing_optional:
            print(f"   - {k}")

    print("✅ Config validated")

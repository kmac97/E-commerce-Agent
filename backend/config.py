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

# Primary model — Perplexity Sonar Pro: built-in live internet search, always current
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "perplexity/sonar-pro")

# Fast model for extraction tasks (no live search needed)
OPENROUTER_FAST_MODEL = os.getenv("OPENROUTER_FAST_MODEL", "meta-llama/llama-3.1-8b-instruct")

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

SHOPIFY_SHOP_URL = os.getenv("SHOPIFY_STORE_URL") or os.getenv("SHOPIFY_SHOP_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOPIFY_API_VERSION = "2024-04"

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

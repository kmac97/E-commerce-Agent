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

# Primary model — Hermes 3 70B is excellent for agentic tool use
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nousresearch/hermes-3-llama-3.1-70b")

# Fallback model for simpler tasks (cheaper)
OPENROUTER_FAST_MODEL = "mistralai/mistral-7b-instruct"

# Model settings
MAX_TOKENS = 2000
TEMPERATURE = 0.7

# ─────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ─────────────────────────────────────────
# SUPABASE
# ─────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ─────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_BASE_URL = "https://google.serper.dev"

# ─────────────────────────────────────────
# SHOPIFY
# ─────────────────────────────────────────

SHOPIFY_SHOP_URL = os.getenv("SHOPIFY_SHOP_URL")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = "2024-01"

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
    }

    optional = {
        "SERPER_API_KEY": SERPER_API_KEY,
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

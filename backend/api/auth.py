# api/auth.py
# Shared API key check for dashboard-facing routers.
# Telegram commands and the cron product-drop call agent functions directly
# in-process (see tgbot/commands.py, tgbot/product_drop.py) -- they never go
# through HTTP, so this only gates the dashboard's fetch calls.

import hmac
from typing import Optional

from fastapi import Header, HTTPException

import config


def is_valid_api_key(provided: Optional[str], expected: Optional[str]) -> bool:
    """Constant-time comparison so a valid key can't be brute-forced via timing."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not is_valid_api_key(x_api_key, config.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

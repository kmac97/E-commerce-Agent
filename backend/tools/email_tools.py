# tools/email_tools.py
# Gmail integration for reading and sending customer emails.
# Phase 5: Full implementation with Gmail OAuth.

# SETUP NOTES:
# 1. Go to console.cloud.google.com
# 2. Create a project → Enable Gmail API
# 3. Create OAuth 2.0 credentials (Desktop app)
# 4. Download credentials.json
# 5. Run the auth flow once to get a refresh token
# 6. Add credentials to .env

import base64
from typing import Optional


async def get_unread_emails(max_results: int = 20) -> list:
    """
    Get unread customer emails from Gmail.
    Phase 5: implement with google-auth and googleapiclient.
    """
    # TODO Phase 5
    return []


async def send_email(to: str, subject: str, body: str) -> bool:
    """
    Send an email via Gmail.
    Phase 5: implement with google-auth and googleapiclient.
    """
    # TODO Phase 5
    return False


async def draft_reply(email_id: str, body: str) -> dict:
    """
    Create a draft reply to an email (for review before sending).
    Phase 5: implement with google-auth and googleapiclient.
    """
    # TODO Phase 5
    return {}


async def label_email(email_id: str, label: str) -> bool:
    """
    Label an email (e.g., 'handled', 'needs-review').
    Phase 5: implement.
    """
    # TODO Phase 5
    return False

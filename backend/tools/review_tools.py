# tools/review_tools.py
# Review monitoring and response tools.
# Phase 5: Full implementation.

# Supports: Shopify native reviews, Judge.me, Loox, Trustpilot
# Start with Judge.me (most common free Shopify review app)

# JUDGE.ME SETUP:
# 1. Install Judge.me on Shopify (free plan available)
# 2. Go to Judge.me dashboard → Settings → API
# 3. Copy your API token and shop domain


async def get_recent_reviews(limit: int = 20, min_rating: int = None) -> list:
    """
    Get recent product reviews.
    Phase 5: implement with Judge.me API.
    """
    # TODO Phase 5
    return []


async def get_negative_reviews(limit: int = 10) -> list:
    """Get reviews with 1-2 star ratings that need attention."""
    # TODO Phase 5
    return []


async def reply_to_review(review_id: str, reply_text: str) -> bool:
    """
    Post a reply to a review.
    Always draft for approval unless auto-reply is explicitly enabled.
    """
    # TODO Phase 5
    return False


async def get_review_summary() -> dict:
    """Get a summary of reviews: average rating, count, recent sentiment."""
    # TODO Phase 5
    return {
        "average_rating": None,
        "total_reviews": 0,
        "positive": 0,
        "negative": 0,
        "needs_reply": 0,
    }

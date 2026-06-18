# tgbot/store_monitor.py
# Scheduled store health checks:
#   - Low stock alerts
#   - Price monitoring with competitor suggestions
# Run via cron or trigger with /inventory and /prices in Telegram.

import asyncio
import logging

import httpx
from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


async def check_low_stock(threshold: int = 10) -> str | None:
    """
    Check Shopify inventory. Returns a formatted alert message if any
    products are below the threshold, otherwise None.
    """
    if not config.SHOPIFY_ACCESS_TOKEN:
        return None

    try:
        from tools.shopify_tools import get_inventory
        low = await get_inventory(threshold=threshold)
        if not low:
            return None

        lines = [f"⚠️ *Low stock alert — {len(low)} item(s) need restocking*\n"]
        for item in low:
            qty = item["quantity"]
            emoji = "🔴" if qty <= 3 else "🟡"
            lines.append(f"{emoji} *{item['title']}* — {qty} units left (${item['price']})")

        lines.append("\n_Review your stock levels in Shopify._")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Low stock check failed: {e}")
        return None


async def get_price_suggestions(limit: int = 5) -> str | None:
    """
    Fetch active products and use Tavily + GPT to suggest price adjustments
    based on current market data.
    """
    if not config.SHOPIFY_ACCESS_TOKEN or not config.TAVILY_API_KEY:
        return None

    try:
        from tools.shopify_tools import get_products
        products = await get_products(limit=limit)
        active = [p for p in products if p.get("status") == "active"]
        if not active:
            return None

        suggestions = []
        async with httpx.AsyncClient(timeout=20) as client:
            for p in active[:3]:  # Limit to 3 to save API credits
                title = p["title"]
                current_price = p.get("variants", [{}])[0].get("price", "?")

                # Quick Tavily search for competitor prices
                try:
                    res = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": config.TAVILY_API_KEY,
                            "query": f"{title} price buy online dropshipping",
                            "search_depth": "basic",
                            "max_results": 3,
                        },
                    )
                    search_data = res.json()
                    snippets = " ".join(
                        r.get("content", "")[:200]
                        for r in search_data.get("results", [])
                    )
                except Exception:
                    snippets = ""

                if snippets:
                    # Ask GPT for a price suggestion
                    gpt_res = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": config.OPENROUTER_MODEL,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": (
                                        f"Product: {title}\n"
                                        f"My current price: ${current_price}\n"
                                        f"Market data: {snippets[:500]}\n\n"
                                        f"In one sentence: should I raise, lower, or keep my price? "
                                        f"Be specific with a suggested price if relevant."
                                    ),
                                }
                            ],
                            "max_tokens": 80,
                            "temperature": 0.5,
                        },
                    )
                    suggestion = gpt_res.json()["choices"][0]["message"]["content"].strip()
                    suggestions.append(f"• *{title}* (${current_price})\n  {suggestion}")

        if not suggestions:
            return None

        lines = ["💰 *Price monitoring report*\n"] + suggestions
        return "\n\n".join(lines)

    except Exception as e:
        logger.error(f"Price suggestions failed: {e}")
        return None


async def optimise_product_listing(product_id: str) -> str:
    """
    Use GPT to rewrite a product's title and description for better conversion,
    then update it on Shopify.
    """
    if not config.SHOPIFY_ACCESS_TOKEN:
        return "Shopify not connected."

    try:
        from tools.shopify_tools import get_products, update_product
        products = await get_products(limit=250)
        product = next((p for p in products if str(p["id"]) == str(product_id)), None)
        if not product:
            return f"Product {product_id} not found."

        current_title = product["title"]
        current_desc = product.get("body_html", "")
        price = product.get("variants", [{}])[0].get("price", "?")

        async with httpx.AsyncClient(timeout=25) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Rewrite this Shopify product listing for better conversion.\n\n"
                                f"Current title: {current_title}\n"
                                f"Current description: {current_desc[:500]}\n"
                                f"Price: ${price}\n\n"
                                f"Return ONLY valid JSON, no markdown:\n"
                                f'{{"title": "improved title", "description": "improved 2-3 sentence description"}}'
                            ),
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
            )
            import re, json
            raw = res.json()["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
            improved = json.loads(raw)

        # Update on Shopify
        await update_product(product_id, {
            "title": improved["title"],
            "body_html": improved["description"],
        })

        return (
            f"✅ *Listing optimised!*\n\n"
            f"*Before:* {current_title}\n"
            f"*After:* {improved['title']}\n\n"
            f"*New description:*\n{improved['description']}"
        )

    except Exception as e:
        logger.error(f"Optimise listing failed: {e}")
        return f"Error optimising listing: {str(e)[:200]}"


async def run_store_monitor():
    """Run all store checks and send alerts if needed."""
    logger.info("Running store monitor...")

    try:
        from database.client import init_db
        await init_db()
    except Exception:
        pass

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

    low_stock_msg = await check_low_stock(threshold=10)
    if low_stock_msg:
        try:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=low_stock_msg,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=low_stock_msg,
                parse_mode=None,
            )

    price_msg = await get_price_suggestions()
    if price_msg:
        try:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=price_msg,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=price_msg,
                parse_mode=None,
            )

    logger.info("Store monitor complete.")


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_store_monitor())

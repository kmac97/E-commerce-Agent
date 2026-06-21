# tgbot/product_drop.py
# Daily auto product drop: runs the find-products agent and Telegrams the results.
# Scheduled via cron (see crontab). Reuses the same agent the dashboard ⚡ Find button uses.

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


def format_drop(found: int, products: list, date_str: str) -> str:
    """Build the Telegram message for the daily product drop. Pure function — testable."""
    if not found:
        return (
            f"🛒 *Morning product drop — {date_str}*\n\n"
            "No fresh winners today — everything I found is already in your pipeline. "
            "Work the ones you've got. 💪"
        )

    lines = [f"🛒 *Morning product drop — {date_str}*\n",
             f"Found *{found}* new product{'s' if found != 1 else ''} for your pipeline:\n"]
    for i, p in enumerate(products, 1):
        name = p.get("name", "Unknown")
        score = f" ⭐{p['score']}/10" if p.get("score") else ""
        lines.append(f"*{i}. {name}*{score}")
        cost, sell, margin = p.get("cost_estimate"), p.get("sell_price_estimate"), p.get("margin_estimate")
        if cost and sell:
            m = f" ({margin}% margin)" if margin else ""
            lines.append(f"   💰 ${cost} → ${sell}{m}")
        if p.get("niche"):
            lines.append(f"   🏷 {p['niche']}")
        if p.get("notes"):
            lines.append(f"   _{p['notes'][:160]}_")
        lines.append("")
    lines.append("→ Review & action them in your dashboard.")
    return "\n".join(lines)


async def send_product_drop():
    """Run the find-products agent and send the results to Telegram."""
    logger.info("Running daily product drop...")

    try:
        from database.client import init_db
        await init_db()
    except Exception:
        pass

    from api.agents import find_products_agent
    result = await find_products_agent()

    if result.get("error"):
        logger.error(f"Product drop failed: {result['error']}")
        return

    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y")
    msg = format_drop(result.get("found", 0), result.get("products", []), date_str)

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        logger.info(f"Product drop sent ({result.get('found', 0)} products).")
    except Exception as e:
        logger.warning(f"Markdown send failed: {e}")
        await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=msg, parse_mode=None)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ponytail: cheap self-check on the only non-trivial logic (formatting)
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        empty = format_drop(0, [], "Sat, 21 Jun 2026")
        assert "No fresh winners" in empty
        full = format_drop(1, [{"name": "Mini Blender", "score": 8, "cost_estimate": 3.5,
                                 "sell_price_estimate": 19.99, "margin_estimate": 82.0,
                                 "niche": "kitchen", "notes": "viral on tiktok"}], "Sat, 21 Jun 2026")
        assert "Mini Blender" in full and "82% margin" in full and "⭐8/10" in full
        print("selftest passed")
        sys.exit(0)

    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(send_product_drop())

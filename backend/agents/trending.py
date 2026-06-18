# agents/trending.py
# Trending product detector.
# Searches multiple sources for what's selling right now,
# scores each opportunity, and reports the top finds.

import asyncio
import logging

import httpx

import config

logger = logging.getLogger(__name__)

TREND_QUERIES = [
    "trending dropshipping products 2026",
    "winning products TikTok shop 2026",
    "best selling Shopify products right now 2026",
    "viral products to sell online 2026",
    "high demand low competition products ecommerce 2026",
]


async def _tavily_search(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Run a single Tavily search and return results."""
    try:
        res = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            },
            timeout=15,
        )
        data = res.json()
        results = []
        if data.get("answer"):
            results.append({"type": "answer", "content": data["answer"]})
        for r in data.get("results", []):
            results.append({
                "type": "result",
                "title": r.get("title", ""),
                "content": r.get("content", "")[:300],
                "url": r.get("url", ""),
            })
        return results
    except Exception as e:
        logger.warning(f"Tavily search failed for '{query}': {e}")
        return []


async def find_trending_products() -> str:
    """
    Search multiple trend sources, extract product opportunities,
    score the top 3, and return a formatted report.
    """
    if not config.TAVILY_API_KEY:
        return "❌ Tavily API key not configured."

    # Run all trend searches in parallel
    async with httpx.AsyncClient() as client:
        search_results = await asyncio.gather(
            *[_tavily_search(client, q) for q in TREND_QUERIES]
        )

    # Flatten all results into one context block
    all_snippets = []
    for results in search_results:
        for r in results:
            if r["type"] == "answer":
                all_snippets.append(r["content"])
            else:
                all_snippets.append(f"{r['title']}: {r['content']}")

    combined = "\n\n".join(all_snippets[:20])  # Keep token usage reasonable

    # Ask GPT to extract and score the top trending products
    prompt = f"""You are a sharp e-commerce product analyst. Based on this real-time web data about trending products in 2026, identify the TOP 3 most promising product opportunities for a new dropshipper.

Web data:
{combined[:3000]}

For each product, provide:
1. Product name
2. Why it's trending right now (1-2 sentences)
3. Estimated selling price range
4. Score out of 10 (for a new seller with $2k budget)
5. Best platform to sell it on (TikTok, Meta, Google)

Format each product clearly with a header like "🔥 Product 1: [name]".
Be specific and use the data provided. Today's date is 2026."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.7,
                },
            )
            report = res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"GPT trending analysis failed: {e}")
        return "❌ Failed to analyse trending products. Try again."

    today = __import__('datetime').date.today()
    return f"🔥 *Trending Products Report*\n_Live data, {today}_\n\n{report}"


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv()

    async def main():
        result = await find_trending_products()
        print(result)

    asyncio.run(main())

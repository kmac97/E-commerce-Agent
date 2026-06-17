# tools/search_tools.py
# Web search tools using Serper API.
# Used by the Researcher agent to find live product and market data.

import httpx
import config


async def web_search(query: str, num_results: int = 10) -> list:
    """
    Search the web using Serper (Google Search API).
    Returns a list of results with title, link, and snippet.
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{config.SERPER_BASE_URL}/search",
            headers={
                "X-API-KEY": config.SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": num_results},
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()

    results = []
    for item in data.get("organic", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet"),
        })
    return results


async def search_tiktok_trends(keyword: str) -> list:
    """Search TikTok-related trends for a product keyword."""
    return await web_search(f"site:tiktok.com {keyword} viral product", num_results=5)


async def search_amazon_bsr(keyword: str) -> list:
    """Search Amazon Best Sellers for a category or keyword."""
    return await web_search(f"amazon best sellers {keyword} 2024", num_results=5)


async def search_aliexpress(keyword: str) -> list:
    """Find product sourcing options on AliExpress."""
    return await web_search(f"aliexpress {keyword} dropshipping price", num_results=5)


async def search_competitor_ads(brand: str) -> list:
    """Search for a competitor's ad angles and marketing."""
    return await web_search(
        f"{brand} facebook ads tiktok ads marketing strategy", num_results=5
    )

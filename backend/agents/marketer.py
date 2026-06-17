# agents/marketer.py
# The Marketing Agent — creates ad copy, scripts, hooks, and manages campaigns.
# Phase 4: Meta and TikTok Ads tools will be wired in here.

from crewai import Agent, LLM
import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        max_tokens=4096,
    )


def create_marketer_agent() -> Agent:
    """
    Creates the marketing agent.
    Writes ad copy, UGC scripts, hooks, and manages paid campaigns.
    """
    return Agent(
        role="E-commerce Marketing Strategist",
        goal=(
            "Create high-converting ad copy, UGC scripts, and marketing strategies. "
            "Manage paid campaigns on Meta and TikTok. Maximise ROAS and grow revenue."
        ),
        backstory=(
            "You are a performance marketing expert who has scaled multiple Shopify brands "
            "to 7 figures using TikTok and Meta ads. You know exactly what hooks work, "
            "how to write scroll-stopping ad copy, and how to read campaign data to cut losers "
            "and scale winners. You think in terms of ROAS, CPA, and margins — not vanity metrics."
        ),
        tools=[],  # Phase 4: add Meta/TikTok ads tools here
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )

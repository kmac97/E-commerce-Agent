# agents/analyst.py
# The Analyst Agent — reviews performance data and gives business intelligence.
# Phase 6: Dashboard data and reporting tools wired in here.

from crewai import Agent, LLM
import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )


def create_analyst_agent() -> Agent:
    """
    Creates the business analyst agent.
    Reviews store metrics, ad performance, and provides P&L insights.
    """
    return Agent(
        role="E-commerce Business Analyst",
        goal=(
            "Analyse business performance data and provide clear, actionable insights. "
            "Track revenue, margins, ad spend, ROAS, and identify trends, anomalies, "
            "and opportunities to improve profitability."
        ),
        backstory=(
            "You are a sharp e-commerce analyst who turns raw data into decisions. "
            "You track the metrics that actually matter — profit, margin, CAC, LTV, ROAS — "
            "and ignore vanity metrics. You spot problems early (rising returns, falling CTR, "
            "thinning margins) and recommend specific actions to fix them. "
            "You deliver daily and weekly briefings that are concise and insight-driven."
        ),
        tools=[],  # Phase 6: add analytics and reporting tools here
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )

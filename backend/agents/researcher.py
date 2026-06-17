# agents/researcher.py
# The Researcher Agent — finds and analyses products, niches, and competitors.

from crewai import Agent, Task, LLM
from crewai_tools import TavilySearchTool

import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )


def create_researcher_agent() -> Agent:
    """
    Creates the product and niche researcher agent.
    This agent searches the web, analyses markets, and scores product ideas.
    """
    search_tool = TavilySearchTool()

    return Agent(
        role="E-commerce Product Researcher",
        goal=(
            "Research e-commerce product ideas and niches thoroughly. "
            "Identify profitable opportunities with strong demand, manageable competition, "
            "good margins, and low risk. Score every product idea from 1-10."
        ),
        backstory=(
            "You are a world-class e-commerce product researcher with 10 years of experience "
            "finding winning products on Shopify, Amazon, and TikTok Shop. "
            "You know how to read market signals, spot trends early, evaluate competition, "
            "estimate margins, and identify products that will actually sell. "
            "You are direct and honest — if a product is bad, you say so and explain why. "
            "You always structure your research clearly with specific numbers and evidence."
        ),
        tools=[search_tool],
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )


def create_research_task(agent: Agent, topic: str, research_type: str = "product") -> Task:
    """
    Creates a research task for a given product or niche.
    """
    if research_type == "competitor":
        description = f"""
        Research the competitor or brand: {topic}

        Investigate and report on:
        1. Their product range and bestsellers
        2. Pricing strategy and margins (estimate)
        3. Their branding and positioning
        4. Their ads and marketing angles (check Meta Ad Library if possible)
        5. Customer reviews — what do people love and hate?
        6. Their weaknesses and gaps we could exploit
        7. Trust signals on their store (reviews, guarantees, social proof)

        Be specific. Use real data where possible.
        End with: 3 concrete ways we could beat this competitor.
        """
    elif research_type == "niche":
        description = f"""
        Research the e-commerce niche: {topic}

        Cover:
        1. Market size and growth trend — is this growing or dying?
        2. Top 3-5 products currently selling well in this niche
        3. Key players and how saturated the market is
        4. Average selling prices and estimated margins
        5. Best platforms (TikTok, Meta, Google, Amazon)
        6. Typical customer profile — who buys in this niche?
        7. Seasonal patterns — does demand spike at certain times?
        8. Entry difficulty — how hard is it to enter this niche?

        Score this niche from 1-10 for a new seller with a $2,000 starting budget.
        Explain your score.
        """
    else:
        # Default: product research
        description = f"""
        Research this e-commerce product idea: {topic}

        Provide a complete analysis structured as follows:

        ## 🧠 Product Potential
        What makes this product interesting or problematic? Score it 1-10 with clear reasoning.

        ## 👤 Target Customer
        Who exactly buys this? Age, gender, pain point, why they buy online.

        ## 🏁 Competition
        How saturated is this market? Who are the main sellers? Is there room for a new brand?

        ## 💰 Pricing & Profit
        Estimated product cost (from AliExpress/CJ Dropshipping), shipping, realistic selling price,
        and expected margin percentage.

        ## ⚠️ Risks
        Seasonal demand? High returns? Fragile shipping? Legal issues? Low barrier to copy?

        ## 📣 Marketing Angles
        Best platforms to sell on. 3 specific marketing angles or hooks that would work for this product.

        ## ✅ Next Steps
        If this scores above 6, what are the immediate next steps to pursue it?

        Use real search data. Be honest and specific.
        """

    return Task(
        description=description,
        agent=agent,
        expected_output=(
            f"A detailed, structured research report on '{topic}' with specific data, "
            f"honest assessment, and clear next steps."
        ),
    )

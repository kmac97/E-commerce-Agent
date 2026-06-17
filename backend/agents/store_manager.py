# agents/store_manager.py
# The Store Manager Agent — manages Shopify listings, orders, and inventory.
# Phase 3: Shopify tools will be wired in here.

from crewai import Agent, LLM
import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )


def create_store_manager_agent() -> Agent:
    """
    Creates the Shopify store manager agent.
    Handles product listings, order monitoring, inventory, and pricing.
    """
    # Phase 3: import and pass Shopify tools here
    # from tools.shopify_tools import (
    #     CreateProductTool, UpdateProductTool, GetOrdersTool, GetInventoryTool
    # )

    return Agent(
        role="Shopify Store Manager",
        goal=(
            "Manage the Shopify store efficiently. Create compelling product listings, "
            "monitor orders and inventory, flag issues, and optimise the store for conversions."
        ),
        backstory=(
            "You are an expert Shopify store manager with deep knowledge of what makes "
            "product listings convert. You write SEO-optimised titles and descriptions, "
            "set competitive prices, and keep the store running smoothly. "
            "You proactively flag low stock, unusual order patterns, and opportunities to improve."
        ),
        tools=[],  # Phase 3: add Shopify tools here
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )

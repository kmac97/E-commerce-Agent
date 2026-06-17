# agents/store_manager.py
# The Store Manager Agent — manages Shopify listings, orders, and inventory.

from crewai import Agent, LLM
import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        max_tokens=4096,
    )


def create_store_manager_agent() -> Agent:
    """
    Creates the Shopify store manager agent.
    Handles product listings, order monitoring, inventory, and pricing.
    """
    tools = []

    if config.SHOPIFY_ACCESS_TOKEN and config.SHOPIFY_SHOP_URL:
        from tools.shopify_tools import (
            GetProductsTool,
            CreateProductTool,
            UpdateProductTool,
            GetOrdersTool,
        )
        tools = [
            GetProductsTool(),
            CreateProductTool(),
            UpdateProductTool(),
            GetOrdersTool(),
        ]

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
        tools=tools,
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )

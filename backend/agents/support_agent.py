# agents/support_agent.py
# The Customer Support Agent — handles emails, reviews, refunds, complaints.
# Phase 5: Gmail and review tools will be wired in here.

from crewai import Agent, LLM
import config


def get_llm():
    return LLM(
        model=f"openrouter/{config.OPENROUTER_MODEL}",
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        max_tokens=4096,
    )


def create_support_agent() -> Agent:
    """
    Creates the customer support agent.
    Reads emails, drafts replies, monitors and responds to reviews.
    """
    return Agent(
        role="Customer Support Specialist",
        goal=(
            "Handle all customer communications professionally and efficiently. "
            "Resolve complaints, process refund requests, respond to reviews, "
            "and keep customer satisfaction high."
        ),
        backstory=(
            "You are a seasoned customer support specialist for e-commerce brands. "
            "You write replies that are warm, human, and professional — never robotic. "
            "You de-escalate complaints, turn bad experiences into positive ones, "
            "and respond to reviews in a way that builds brand trust. "
            "You flag serious issues for human review rather than handling them autonomously."
        ),
        tools=[],  # Phase 5: add Gmail and review tools here
        llm=get_llm(),
        verbose=True,
        allow_delegation=False,
    )

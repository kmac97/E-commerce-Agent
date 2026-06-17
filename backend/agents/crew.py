# agents/crew.py
# The main orchestrator. Creates the crew and kicks off tasks.

import logging
from datetime import datetime

from crewai import Crew, Process

from agents.researcher import create_researcher_agent, create_research_task
from agents.store_manager import create_store_manager_agent
from agents.marketer import create_marketer_agent
from agents.support_agent import create_support_agent
from agents.analyst import create_analyst_agent
from database.client import save_task_log, update_task_log, save_research
from tgbot.bot import send_telegram_message

logger = logging.getLogger(__name__)


async def run_research_task(task_id: str, topic: str, research_type: str = "product"):
    """
    Run a full product/niche research task using the researcher agent.
    Saves results to Supabase and sends a Telegram notification when done.
    """
    start_time = datetime.now()

    # Log task start
    await save_task_log(
        task_id=task_id,
        agent="researcher",
        task=f"Research {research_type}: {topic}",
        status="running",
        input={"topic": topic, "type": research_type},
    )

    await send_telegram_message(f"🔍 Research started: *{topic}*\nI'll notify you when done.")

    try:
        # Create the researcher agent and task
        researcher = create_researcher_agent()
        research_task = create_research_task(researcher, topic, research_type)

        # Run the crew
        crew = Crew(
            agents=[researcher],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True,
        )

        result = await crew.kickoff_async()
        result_text = str(result)

        # Calculate duration
        duration = int((datetime.now() - start_time).total_seconds())

        # Save research to Supabase
        await save_research(
            type=research_type,
            topic=topic,
            data={"raw_output": result_text},
        )

        # Update task log
        await update_task_log(
            task_id=task_id,
            status="complete",
            output={"result": result_text},
            duration_seconds=duration,
        )

        # Send Telegram notification with summary
        summary = result_text[:800] + "..." if len(result_text) > 800 else result_text
        await send_telegram_message(
            f"✅ Research complete: *{topic}*\n\n{summary}\n\n"
            f"_Full results saved to dashboard._"
        )

        logger.info(f"Research task {task_id} completed in {duration}s")

    except Exception as e:
        logger.error(f"Research task {task_id} failed: {e}")

        await update_task_log(
            task_id=task_id,
            status="failed",
            error=str(e),
        )

        await send_telegram_message(
            f"❌ Research failed for *{topic}*\n\nError: {str(e)[:200]}"
        )


def build_full_crew():
    """
    Build the full crew with all agents.
    Used for complex multi-agent tasks in later phases.
    """
    return Crew(
        agents=[
            create_researcher_agent(),
            create_store_manager_agent(),
            create_marketer_agent(),
            create_support_agent(),
            create_analyst_agent(),
        ],
        process=Process.hierarchical,
        verbose=True,
    )

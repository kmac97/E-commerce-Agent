# agents/job_worker.py
# Durable job queue worker (Phase 1.5). Replaces asyncio.create_task/
# BackgroundTasks for run_research_task, which would otherwise silently
# vanish if the web process restarts mid-task.
#
# ponytail: one polling loop in the same process, matching the actual
# deployment (one VPS, one PM2 process) -- no separate worker process, no
# multi-worker coordination. Upgrade if this ever needs to scale beyond one
# instance (see database/client.py's claim_next_job for the specific note).

import asyncio
import logging

from database.client import claim_next_job, mark_job_complete, mark_job_failed, reclaim_orphaned_jobs

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
ORPHAN_TIMEOUT_MINUTES = 30

# Populated by register_job_handler() -- kept as a plain dict rather than
# importing agents.crew directly here, so this module has no dependency on
# any specific job type and doesn't risk a circular import.
JOB_HANDLERS = {}


def register_job_handler(job_type: str, handler):
    JOB_HANDLERS[job_type] = handler


async def _run_one(job: dict):
    handler = JOB_HANDLERS.get(job["type"])
    if not handler:
        await mark_job_failed(job["id"], f"No handler registered for job type '{job['type']}'")
        return
    try:
        await handler(**job["payload"])
        await mark_job_complete(job["id"])
    except Exception as e:
        logger.error(f"Job {job['id']} ({job['type']}) failed: {e}")
        await mark_job_failed(job["id"], str(e))


async def run_worker_loop():
    """Long-running polling loop -- started once at app startup alongside the
    Telegram bot (see main.py)."""
    reclaimed = await reclaim_orphaned_jobs(timeout_minutes=ORPHAN_TIMEOUT_MINUTES)
    if reclaimed:
        logger.warning(f"Reclaimed {reclaimed} orphaned job(s) from a previous process")
    logger.info("Job worker loop started")

    while True:
        try:
            job = await claim_next_job()
            if job:
                await _run_one(job)
            else:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Job worker loop error: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

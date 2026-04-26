"""Iteration synthesis workflow.

Trigger: After refresh or feedback
Main Hindsight operations: recall, reflect
Output: Iteration headers and next-test backlog
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput
from app.workers.iteration_planner import IterationPlannerWorker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.orchestrator.workflows.iteration_synthesis.run_iteration_synthesis",
    bind=True,
)
def run_iteration_synthesis(
    self,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_iteration_synthesis_async(self.request.id, account_id, offer_id, payload)
    )


async def _run_iteration_synthesis_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    step_log: list[dict] = []

    step_log.append(build_step_log_entry("iteration_synthesis", "started"))

    planner = IterationPlannerWorker()
    result = await planner.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params=payload,
    ))

    step_log.append(build_step_log_entry("iteration_synthesis", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": result.data,
        "step_log": step_log,
    }

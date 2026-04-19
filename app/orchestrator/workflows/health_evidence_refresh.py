"""Health evidence refresh workflow.

Trigger: Cron or manual
Main Hindsight operations: retain, reflect
Output: New literature summary and compliance signals
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput
from app.workers.domain_research import DomainResearchWorker

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.orchestrator.workflows.health_evidence_refresh.run_health_refresh",
    bind=True,
)
def run_health_refresh(
    self,
    account_id: str,
    offer_id: str,
    queries: list[str],
) -> dict[str, Any]:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_health_refresh_async(self.request.id, account_id, offer_id, queries)
    )


async def _run_health_refresh_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    queries: list[str],
) -> dict[str, Any]:
    step_log: list[dict] = []

    step_log.append(build_step_log_entry("health_evidence_refresh", "started"))

    worker = DomainResearchWorker()
    result = await worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={"queries": queries, "domain": "health"},
    ))

    step_log.append(build_step_log_entry("health_evidence_refresh", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": result.data,
        "requires_review": result.requires_review,
        "step_log": step_log,
    }

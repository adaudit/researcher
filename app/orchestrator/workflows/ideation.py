"""Ideation workflow (STORMING) — raw sources → brief pack.

Chain: organic_discovery + swipe_miner (parallel) → coverage_matrix →
       hook_engineer → brief_composer

Input:  Platform search params, competitor queries, niche keywords
Output: brief_pack ready for the writing workflow
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.ideation.run_ideation_workflow", bind=True)
def run_ideation_workflow(
    self,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute the complete ideation pipeline."""
    import asyncio as _asyncio
    return _asyncio.get_event_loop().run_until_complete(
        _run_ideation_async(self.request.id, account_id, offer_id, payload)
    )


async def _run_ideation_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from app.workers.brief_composer import BriefComposerWorker
    from app.workers.coverage_matrix import CoverageMatrixWorker
    from app.workers.hook_engineer import HookEngineerWorker
    from app.workers.organic_discovery import OrganicDiscoveryWorker
    from app.workers.swipe_miner import SwipeMinerWorker

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    # Step 1: Parallel — organic discovery + swipe mining
    step_log.append(build_step_log_entry("organic_discovery", "started"))
    step_log.append(build_step_log_entry("swipe_miner", "started"))

    organic_worker = OrganicDiscoveryWorker()
    swipe_worker = SwipeMinerWorker()

    organic_task = organic_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "platform_searches": payload.get("platform_searches", []),
            "niche_keywords": payload.get("niche_keywords", []),
            "content_items": payload.get("organic_content", []),
        },
    ))

    swipe_task = swipe_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "competitor_queries": payload.get("competitor_queries", []),
            "ad_library_data": payload.get("ad_library_data", []),
        },
    ))

    organic_result, swipe_result = await asyncio.gather(organic_task, swipe_task)
    results["organic_seeds"] = organic_result.data
    results["swipe_analysis"] = swipe_result.data
    step_log.append(build_step_log_entry("organic_discovery", "completed"))
    step_log.append(build_step_log_entry("swipe_miner", "completed"))

    # Step 2: Coverage matrix analysis
    step_log.append(build_step_log_entry("coverage_matrix", "started"))
    coverage_worker = CoverageMatrixWorker()
    coverage_result = await coverage_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "performance_data": payload.get("performance_data", {}),
        },
    ))
    results["coverage_matrix"] = coverage_result.data
    step_log.append(build_step_log_entry("coverage_matrix", "completed"))

    # Step 3: Hook engineering (informed by coverage gaps)
    step_log.append(build_step_log_entry("hook_engineer", "started"))
    hook_worker = HookEngineerWorker()
    hook_result = await hook_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "desire_map": payload.get("desire_map", {}),
            "proof_inventory": payload.get("proof_inventory", {}),
            "differentiation_map": payload.get("differentiation_map", {}),
        },
    ))
    results["hook_territory_map"] = hook_result.data
    step_log.append(build_step_log_entry("hook_engineer", "completed"))

    # Step 4: Brief composition
    step_log.append(build_step_log_entry("brief_composer", "started"))
    brief_worker = BriefComposerWorker()
    brief_result = await brief_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "hook_territory_map": hook_result.data.get("hook_territory_map", {}),
            "seeds": payload.get("seeds", []),
        },
    ))
    results["brief_pack"] = brief_result.data
    step_log.append(build_step_log_entry("brief_composer", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }

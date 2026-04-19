"""Full cycle workflow — the complete 90-minute creative strategy cycle.

Chain: Analysis (onboarding) → Ideation → Writing → Creative → Reflection

This is the end-to-end pipeline that takes an offer from raw inputs
to finished ad copies with image prompts, compounding intelligence
via Hindsight memory at every stage.
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.full_cycle.run_full_cycle", bind=True)
def run_full_cycle(
    self,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute the complete creative strategy cycle."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_full_cycle_async(self.request.id, account_id, offer_id, payload)
    )


async def _run_full_cycle_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from app.orchestrator.workflows.creative import _run_creative_async
    from app.orchestrator.workflows.ideation import _run_ideation_async
    from app.orchestrator.workflows.onboarding import _run_onboarding_async
    from app.orchestrator.workflows.writing import _run_writing_async
    from app.workers.memory_reflection import MemoryReflectionWorker

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    # Phase 1: Analysis (onboarding — offer decomposition, audience, proof, differentiation)
    step_log.append(build_step_log_entry("analysis_phase", "started"))
    analysis = await _run_onboarding_async(
        task_id=f"{task_id}_analysis",
        account_id=account_id,
        offer_id=offer_id,
        payload=payload,
    )
    results["analysis"] = analysis.get("results", {})
    step_log.append(build_step_log_entry("analysis_phase", "completed"))

    # Phase 2: Ideation (STORMING — organic discovery, swipe mining, coverage matrix, hooks, briefs)
    step_log.append(build_step_log_entry("ideation_phase", "started"))
    ideation_payload = {
        **payload,
        "desire_map": results["analysis"].get("desire_map", {}),
        "proof_inventory": results["analysis"].get("proof_inventory", {}),
        "differentiation_map": results["analysis"].get("differentiation_map", {}),
    }
    ideation = await _run_ideation_async(
        task_id=f"{task_id}_ideation",
        account_id=account_id,
        offer_id=offer_id,
        payload=ideation_payload,
    )
    results["ideation"] = ideation.get("results", {})
    step_log.append(build_step_log_entry("ideation_phase", "completed"))

    # Phase 3: Writing (hooks → copy → police → compress → headlines)
    step_log.append(build_step_log_entry("writing_phase", "started"))
    brief_pack = results["ideation"].get("brief_pack", {})
    writing = await _run_writing_async(
        task_id=f"{task_id}_writing",
        account_id=account_id,
        offer_id=offer_id,
        brief_pack=brief_pack,
    )
    results["writing"] = writing.get("results", {})
    step_log.append(build_step_log_entry("writing_phase", "completed"))

    # Phase 4: Creative (SCRAWLS — image concepts → image prompts)
    step_log.append(build_step_log_entry("creative_phase", "started"))
    drafts = results["writing"].get("copy_drafts", {}).get("copy_drafts", {}).get("drafts", [])
    if drafts:
        creative = await _run_creative_async(
            task_id=f"{task_id}_creative",
            account_id=account_id,
            offer_id=offer_id,
            ad_copies=drafts,
            target_tool=payload.get("target_tool", "midjourney"),
        )
        results["creative"] = creative.get("results", {})
    step_log.append(build_step_log_entry("creative_phase", "completed"))

    # Phase 5: Reflection — compound learnings from the full cycle
    step_log.append(build_step_log_entry("reflection_phase", "started"))
    reflection_worker = MemoryReflectionWorker()
    reflection_result = await reflection_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "reflection_prompt": (
                "Reflect on the full creative cycle just completed. "
                "What strategic positions are strongest? Where are the "
                "biggest evidence gaps? What should the next cycle prioritize?"
            ),
        },
    ))
    results["cycle_reflection"] = reflection_result.data
    step_log.append(build_step_log_entry("reflection_phase", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "phase_count": 5,
        "results": results,
        "step_log": step_log,
    }

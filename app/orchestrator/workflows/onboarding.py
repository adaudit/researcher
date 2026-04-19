"""Account onboarding research workflow.

Trigger: Manual, API, or UI
Main Hindsight operations: retain, recall, reflect
Output: Baseline strategy pack

Flow:
  1. Ingest offer and assets → acquisition workers
  2. Normalize artifacts → normalization layer
  3. Retain strategic knowledge → worker runtime + Hindsight
  4. Extract observations and maps → specialist workers + recall
  5. Build strategy maps and briefs → synthesis workers + recall + reflect
  6. Create reflection candidates → reflection worker + reflect
  7. Publish baseline pack → orchestrator
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.audience_psychology import AudiencePsychologyWorker
from app.workers.base import WorkerInput
from app.workers.brief_composer import BriefComposerWorker
from app.workers.differentiation import DifferentiationWorker
from app.workers.hook_engineer import HookEngineerWorker
from app.workers.memory_reflection import MemoryReflectionWorker
from app.workers.offer_intelligence import OfferIntelligenceWorker
from app.workers.proof_inventory import ProofInventoryWorker

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.onboarding.run_onboarding", bind=True)
def run_onboarding(self, account_id: str, offer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the full onboarding research workflow."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_onboarding_async(self.request.id, account_id, offer_id, payload)
    )


async def _run_onboarding_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    step_log: list[dict] = []
    results: dict[str, Any] = {}

    base_input = WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params=payload,
    )

    # Step 1: Offer intelligence
    step_log.append(build_step_log_entry("offer_intelligence", "started"))
    offer_worker = OfferIntelligenceWorker()
    offer_result = await offer_worker.run(base_input)
    results["offer_map"] = offer_result.data
    step_log.append(build_step_log_entry("offer_intelligence", "completed"))

    # Step 2: Audience psychology (desire map)
    step_log.append(build_step_log_entry("audience_psychology", "started"))
    audience_worker = AudiencePsychologyWorker()
    audience_result = await audience_worker.run(base_input)
    results["desire_map"] = audience_result.data
    step_log.append(build_step_log_entry("audience_psychology", "completed"))

    # Step 3: Proof inventory
    step_log.append(build_step_log_entry("proof_inventory", "started"))
    proof_worker = ProofInventoryWorker()
    proof_result = await proof_worker.run(base_input)
    results["proof_inventory"] = proof_result.data
    step_log.append(build_step_log_entry("proof_inventory", "completed"))

    # Step 4: Differentiation
    step_log.append(build_step_log_entry("differentiation", "started"))
    diff_worker = DifferentiationWorker()
    diff_result = await diff_worker.run(base_input)
    results["differentiation_map"] = diff_result.data
    step_log.append(build_step_log_entry("differentiation", "completed"))

    # Step 5: Hook engineering
    step_log.append(build_step_log_entry("hook_engineer", "started"))
    hook_input = WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "desire_map": audience_result.data.get("desire_map", {}),
            **payload,
        },
    )
    hook_worker = HookEngineerWorker()
    hook_result = await hook_worker.run(hook_input)
    results["hook_territory_map"] = hook_result.data
    step_log.append(build_step_log_entry("hook_engineer", "completed"))

    # Step 6: Brief composition
    step_log.append(build_step_log_entry("brief_composer", "started"))
    brief_input = WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "strategy_map": {
                **offer_result.data.get("offer_map", {}),
                "proof_hierarchy": proof_result.data.get("proof_hierarchy", {}),
            },
            "seeds": payload.get("seeds", []),
        },
    )
    brief_worker = BriefComposerWorker()
    brief_result = await brief_worker.run(brief_input)
    results["brief_pack"] = brief_result.data
    step_log.append(build_step_log_entry("brief_composer", "completed"))

    # Step 7: Memory reflection (baseline)
    step_log.append(build_step_log_entry("memory_reflection", "started"))
    reflection_worker = MemoryReflectionWorker()
    reflection_result = await reflection_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "reflection_prompt": (
                "Analyze the baseline evidence gathered during onboarding. "
                "Identify the strongest strategic positions and the biggest "
                "gaps in evidence or proof."
            )
        },
    ))
    results["baseline_reflection"] = reflection_result.data
    step_log.append(build_step_log_entry("memory_reflection", "completed"))

    # Initialize per-account skills and template library
    try:
        from app.services.intelligence.skill_manager import skill_manager
        await skill_manager.initialize_skills(account_id)
        step_log.append(build_step_log_entry("skill_init", "completed"))
    except Exception:
        step_log.append(build_step_log_entry("skill_init", "skipped"))

    try:
        from app.services.intelligence.template_library import template_library
        await template_library.initialize_global_templates()
        step_log.append(build_step_log_entry("template_init", "completed"))
    except Exception:
        step_log.append(build_step_log_entry("template_init", "skipped"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }

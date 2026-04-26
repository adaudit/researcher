"""Full cycle workflow — creative strategy with approval gate.

Two-phase design:
  Phase A (run_full_cycle):
    Analysis → Ideation → creates approval record → STOPS
  Phase B (dispatch_writing_phase):
    Writing → Creative → Reflection — triggered ONLY by approval

This ensures no copy/creative is generated until a human reviews and
approves the angle ideas and briefs from ideation.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


# ── Phase A: Analysis + Ideation → approval gate ─────────────────


@celery_app.task(
    name="app.orchestrator.workflows.full_cycle.run_full_cycle",
    bind=True,
)
def run_full_cycle(
    self,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run analysis + ideation, then stop and create an approval record."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_ideation_phase_async(self.request.id, account_id, offer_id, payload)
    )


async def _run_ideation_phase_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from app.orchestrator.workflows.ideation import _run_ideation_async
    from app.orchestrator.workflows.onboarding import _run_onboarding_async

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    # Phase 1: Analysis
    step_log.append(build_step_log_entry("analysis_phase", "started"))
    analysis = await _run_onboarding_async(
        task_id=f"{task_id}_analysis",
        account_id=account_id,
        offer_id=offer_id,
        payload=payload,
    )
    results["analysis"] = analysis.get("results", {})
    step_log.append(build_step_log_entry("analysis_phase", "completed"))

    # Phase 2: Ideation (STORMING)
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

    # ── APPROVAL GATE ─────────────────────────────────────────────
    # Create approval records for the ideation outputs. The writing
    # phase will NOT run until these are approved via the API.
    approval_ids = await _create_ideation_approvals(
        account_id, offer_id, task_id, results,
    )
    step_log.append(build_step_log_entry(
        "approval_gate", "awaiting_approval",
        f"Created {len(approval_ids)} approvals",
    ))

    logger.info(
        "full_cycle.paused_for_approval workflow=%s approvals=%s",
        task_id, approval_ids,
    )

    return {
        "workflow_id": task_id,
        "status": "awaiting_approval",
        "phase_count": 2,
        "approval_ids": approval_ids,
        "results": results,
        "step_log": step_log,
    }


async def _create_ideation_approvals(
    account_id: str,
    offer_id: str,
    workflow_job_id: str,
    results: dict[str, Any],
) -> list[str]:
    """Create approval records for ideation outputs."""
    from app.db.models.approval import Approval
    from app.db.session import async_session_factory

    approval_ids: list[str] = []

    async with async_session_factory() as db:
        # Angle/hook territory approval
        hook_territory = results.get("ideation", {}).get("hook_territory_map", {})
        if hook_territory:
            approval = Approval(
                id=f"appr_{uuid4().hex[:12]}",
                account_id=account_id,
                offer_id=offer_id,
                approval_type="angle_approval",
                status="pending",
                workflow_job_id=workflow_job_id,
                payload={
                    "hook_territory_map": hook_territory,
                    "type": "angles",
                },
            )
            db.add(approval)
            approval_ids.append(approval.id)

        # Brief pack approval
        brief_pack = results.get("ideation", {}).get("brief_pack", {})
        if brief_pack:
            approval = Approval(
                id=f"appr_{uuid4().hex[:12]}",
                account_id=account_id,
                offer_id=offer_id,
                approval_type="brief_approval",
                status="pending",
                workflow_job_id=workflow_job_id,
                payload={
                    "brief_pack": brief_pack,
                    "type": "briefs",
                },
            )
            db.add(approval)
            approval_ids.append(approval.id)

        if approval_ids:
            await db.commit()

    return approval_ids


# ── Phase B: Writing + Creative + Reflection ─────────────────────


@celery_app.task(
    name="app.orchestrator.workflows.full_cycle.dispatch_writing_phase",
    bind=True,
)
def dispatch_writing_phase(
    self,
    account_id: str,
    offer_id: str,
    workflow_job_id: str,
    approved_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume the full cycle after approval — runs writing + creative + reflection."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_writing_phase_async(
            self.request.id, account_id, offer_id,
            workflow_job_id, approved_payload or {},
        )
    )


async def _run_writing_phase_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    workflow_job_id: str,
    approved_payload: dict[str, Any],
) -> dict[str, Any]:
    from app.orchestrator.workflows.creative import _run_creative_async
    from app.orchestrator.workflows.writing import _run_writing_async
    from app.workers.memory_reflection import MemoryReflectionWorker

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    brief_pack = approved_payload.get("brief_pack", {})

    # Phase 3: Writing (hooks → copy → police → compress → headlines)
    step_log.append(build_step_log_entry("writing_phase", "started"))
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
    drafts = (
        results["writing"]
        .get("copy_drafts", {})
        .get("copy_drafts", {})
        .get("drafts", [])
    )
    if drafts:
        creative = await _run_creative_async(
            task_id=f"{task_id}_creative",
            account_id=account_id,
            offer_id=offer_id,
            ad_copies=drafts,
            target_tool="midjourney",
        )
        results["creative"] = creative.get("results", {})
    step_log.append(build_step_log_entry("creative_phase", "completed"))

    # Phase 5: Reflection
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

    logger.info(
        "full_cycle.writing_phase_complete workflow=%s parent=%s",
        task_id, workflow_job_id,
    )

    return {
        "workflow_id": task_id,
        "parent_workflow_id": workflow_job_id,
        "status": "completed",
        "phase_count": 3,
        "results": results,
        "step_log": step_log,
    }

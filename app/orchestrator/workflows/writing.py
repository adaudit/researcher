"""Writing workflow — brief → finished ad copies.

Chain: hook_generator → copy_generator → copy_shape_police →
       compression_tax → headline_generator

Input:  brief_pack (from ideation workflow or manual)
Output: Finished ad copies with hooks and headlines
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.writing.run_writing_workflow", bind=True)
def run_writing_workflow(
    self,
    account_id: str,
    offer_id: str,
    brief_pack: dict[str, Any],
) -> dict[str, Any]:
    """Execute the complete writing pipeline."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_writing_async(self.request.id, account_id, offer_id, brief_pack)
    )


async def _run_writing_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    brief_pack: dict[str, Any],
) -> dict[str, Any]:
    from app.workers.compression_tax import CompressionTaxWorker
    from app.workers.copy_generator import CopyGeneratorWorker
    from app.workers.copy_shape_police import CopyShapePoliceWorker
    from app.workers.headline_generator import HeadlineGeneratorWorker
    from app.workers.hook_generator import HookGeneratorWorker

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    # Step 1: Generate hooks
    step_log.append(build_step_log_entry("hook_generator", "started"))
    hook_worker = HookGeneratorWorker()
    hook_result = await hook_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={"brief_pack": brief_pack},
    ))
    results["hooks"] = hook_result.data
    step_log.append(build_step_log_entry("hook_generator", "completed"))

    # Step 2: Generate ad copy drafts
    step_log.append(build_step_log_entry("copy_generator", "started"))
    copy_worker = CopyGeneratorWorker()
    copy_result = await copy_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={"brief_pack": brief_pack},
    ))
    results["copy_drafts"] = copy_result.data
    step_log.append(build_step_log_entry("copy_generator", "completed"))

    # Step 3: Copy shape police review
    drafts = copy_result.data.get("copy_drafts", {}).get("drafts", [])
    reviewed_drafts: list[dict[str, Any]] = []
    police_worker = CopyShapePoliceWorker()

    for draft in drafts:
        draft_text = f"{draft.get('hook', '')}\n\n{draft.get('body', '')}\n\n{draft.get('cta', '')}"
        step_log.append(build_step_log_entry("copy_shape_police", "started"))
        review_result = await police_worker.run(WorkerInput(
            account_id=account_id,
            offer_id=offer_id,
            params={"draft_text": draft_text},
        ))
        reviewed_drafts.append({
            "draft": draft,
            "review": review_result.data,
        })
        step_log.append(build_step_log_entry("copy_shape_police", "completed"))

    results["reviewed_drafts"] = reviewed_drafts

    # Step 4: Compression tax on each draft
    compressed_drafts: list[dict[str, Any]] = []
    compress_worker = CompressionTaxWorker()

    for draft in drafts:
        draft_text = f"{draft.get('hook', '')}\n\n{draft.get('body', '')}\n\n{draft.get('cta', '')}"
        step_log.append(build_step_log_entry("compression_tax", "started"))
        compress_result = await compress_worker.run(WorkerInput(
            account_id=account_id,
            offer_id=offer_id,
            params={"draft_text": draft_text},
        ))
        compressed_drafts.append({
            "original_draft": draft,
            "compressed": compress_result.data,
        })
        step_log.append(build_step_log_entry("compression_tax", "completed"))

    results["compressed_drafts"] = compressed_drafts

    # Step 5: Generate headlines for each draft
    headline_worker = HeadlineGeneratorWorker()
    headlines_per_draft: list[dict[str, Any]] = []

    for i, draft in enumerate(drafts):
        step_log.append(build_step_log_entry("headline_generator", "started"))
        headline_result = await headline_worker.run(WorkerInput(
            account_id=account_id,
            offer_id=offer_id,
            params={"ad_copy": draft},
        ))
        headlines_per_draft.append({
            "draft_index": i,
            "headlines": headline_result.data,
        })
        step_log.append(build_step_log_entry("headline_generator", "completed"))

    results["headlines"] = headlines_per_draft

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }

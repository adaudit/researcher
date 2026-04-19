"""Creative workflow (SCRAWLS) — finished ad copies → image prompts.

Chain: image_concept_generator → image_prompt_generator

Input:  Finished ad copies from the writing workflow
Output: Image prompts ready for Midjourney/GPT-Image generation tools
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.creative.run_creative_workflow", bind=True)
def run_creative_workflow(
    self,
    account_id: str,
    offer_id: str,
    ad_copies: list[dict[str, Any]],
    target_tool: str = "midjourney",
) -> dict[str, Any]:
    """Execute the creative image pipeline."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_creative_async(self.request.id, account_id, offer_id, ad_copies, target_tool)
    )


async def _run_creative_async(
    task_id: str,
    account_id: str,
    offer_id: str,
    ad_copies: list[dict[str, Any]],
    target_tool: str,
) -> dict[str, Any]:
    from app.workers.image_concept_generator import ImageConceptGeneratorWorker
    from app.workers.image_prompt_generator import ImagePromptGeneratorWorker

    step_log: list[dict] = []
    results: dict[str, Any] = {}

    all_concepts: list[dict[str, Any]] = []

    # Step 1: Generate image concepts for each ad copy
    concept_worker = ImageConceptGeneratorWorker()
    for i, copy_data in enumerate(ad_copies):
        step_log.append(build_step_log_entry("image_concept_generator", "started"))
        concept_result = await concept_worker.run(WorkerInput(
            account_id=account_id,
            offer_id=offer_id,
            params={"ad_copy": copy_data},
        ))
        concepts = concept_result.data.get("image_concepts", {}).get("concepts", [])
        all_concepts.extend(concepts)
        step_log.append(build_step_log_entry("image_concept_generator", "completed"))

    results["all_concepts"] = all_concepts
    results["concept_count"] = len(all_concepts)

    # Select top concepts by scroll-stop score (top 15)
    sorted_concepts = sorted(
        all_concepts,
        key=lambda c: c.get("scroll_stop_score", 0),
        reverse=True,
    )
    selected = sorted_concepts[:15]
    results["selected_concepts"] = selected

    # Step 2: Generate image prompts for selected concepts
    step_log.append(build_step_log_entry("image_prompt_generator", "started"))
    prompt_worker = ImagePromptGeneratorWorker()
    prompt_result = await prompt_worker.run(WorkerInput(
        account_id=account_id,
        offer_id=offer_id,
        params={
            "image_concepts": selected,
            "target_tool": target_tool,
        },
    ))
    results["image_prompts"] = prompt_result.data
    step_log.append(build_step_log_entry("image_prompt_generator", "completed"))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }

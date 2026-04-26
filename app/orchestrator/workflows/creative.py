"""Creative workflow (SCRAWLS) — finished ad copies → image concepts → prompts → images.

Chain: image_concept_generator → image_prompt_generator → image_generator (optional)

Input:  Finished ad copies from the writing workflow
Output: Image prompts + optionally generated images (Flux/GPT-Image/Ideogram)
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

    # Step 3 (optional): Generate actual images if generate_images=True
    generate_images = ad_copies[0].get("generate_images", False) if ad_copies else False
    if generate_images:
        step_log.append(build_step_log_entry("image_generation", "started"))
        try:
            from app.services.creative.image_generator import ImageProvider, image_generator

            prompts_data = prompt_result.data.get("image_prompts", {}).get("prompts", [])
            provider = ad_copies[0].get("image_provider", "flux_pro") if ad_copies else "flux_pro"

            gen_requests = [
                {
                    "prompt": p.get("prompt", ""),
                    "provider": provider,
                    "aspect_ratio": p.get("format", "1:1"),
                    "negative_prompt": p.get("negative_constraints"),
                }
                for p in prompts_data[:10]
            ]

            gen_results = await image_generator.generate_batch(
                gen_requests, default_provider=ImageProvider(provider),
            )

            results["generated_images"] = [
                {
                    "provider": r.provider,
                    "image_url": r.image_url,
                    "width": r.width,
                    "height": r.height,
                    "cost": r.cost,
                    "error": r.error,
                }
                for r in gen_results
            ]
            results["generation_cost"] = sum(r.cost for r in gen_results)
            results["images_generated"] = sum(1 for r in gen_results if r.image_url)

            step_log.append(build_step_log_entry(
                "image_generation", "completed",
                f"Generated {results['images_generated']} images, cost=${results['generation_cost']:.2f}",
            ))
        except Exception as exc:
            logger.warning("creative.image_generation_failed error=%s", exc)
            step_log.append(build_step_log_entry(
                "image_generation", "failed", str(exc)[:200],
            ))

    return {
        "workflow_id": task_id,
        "status": "completed",
        "results": results,
        "step_log": step_log,
    }

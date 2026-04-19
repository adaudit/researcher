"""Image Concept Generator — generates 30-50 visual concepts from multiple sources.

Input:  Finished ad copy
Output: Raw image concepts ranked by scroll-stop potential
Banks:  recall from CREATIVE, VOC, OFFER
Sources: Copy-derived, reptile triggers, audience language, wild associations
"""

from __future__ import annotations

import json

from app.knowledge.base_training import get_training_context
from app.prompts.systems import IMAGE_CONCEPT_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.router import Capability, router
from app.services.llm.schemas import IMAGE_CONCEPT_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class ImageConceptGeneratorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="image_concept_generator",
        purpose="Generate 30-50 image concepts from multiple creative sources",
        accepted_input_types=["ad_copy", "brief"],
        recall_scope=[BankType.CREATIVE, BankType.VOC, BankType.OFFER],
        write_scope=[],
        steps=[
            "recall_creative_and_voc_context",
            "llm_generate_copy_derived_concepts",
            "llm_generate_reptile_trigger_concepts",
            "llm_generate_audience_language_concepts",
            "llm_generate_wild_associations",
            "rank_by_scroll_stop_potential",
        ],
        quality_checks=[
            "concepts_from_multiple_sources_required",
            "scroll_stop_potential_must_be_assessed",
            "native_feed_fit_must_be_assessed",
            "format_suitability_must_be_specified",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall relevant context
        memories = await recall_for_worker(
            "image_concept_generator",
            account_id,
            "creative visual image ad winning concept audience desire pain exact phrase",
            offer_id=offer_id,
            top_k=30,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Ad copy input
        ad_copy = params.get("ad_copy", "")
        if isinstance(ad_copy, dict):
            ad_copy = json.dumps(ad_copy, indent=1, default=str)

        brief = params.get("brief", {})
        brief_text = json.dumps(brief, indent=1, default=str) if brief else ""

        training_context = get_training_context()
        result = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=f"{IMAGE_CONCEPT_GENERATOR_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Generate 30-50 image concepts for this ad copy.\n\n"
                f"AD COPY:\n{ad_copy}\n\n"
                f"{'BRIEF:' + chr(10) + brief_text + chr(10) + chr(10) if brief_text else ''}"
                f"CONTEXT ({len(memories)} recalled items):\n{evidence_text}\n\n"
                f"Generate concepts from ALL source categories:\n"
                f"1. Copy-derived (literal visualization of the copy)\n"
                f"2. Reptile triggers (primal psychological reactions)\n"
                f"3. Audience language (turn VOC phrases into visual scenes)\n"
                f"4. Wild associations (unexpected metaphors/juxtapositions)\n\n"
                f"Score each concept for scroll-stop potential (1-10) and native-feed fit (1-10). "
                f"Include production feasibility for each."
            ),
            temperature=0.8,  # High creativity for visual concepts
            max_tokens=8000,
            json_schema=IMAGE_CONCEPT_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Multi-pass refinement
        max_passes = params.get("max_passes", 2)
        quality_threshold = params.get("quality_threshold", 7.5)
        if max_passes > 0 and result.get("concepts"):
            from app.services.intelligence.refinement_engine import refinement_engine
            refinement = await refinement_engine.refine(
                task_type="image_concept_generation",
                initial_output=result,
                system_prompt=f"{IMAGE_CONCEPT_GENERATOR_SYSTEM}\n\n{training_context}",
                context=f"AD COPY:\n{ad_copy[:2000]}\n\nEVIDENCE:\n{evidence_text[:3000]}",
                max_passes=max_passes,
                threshold=quality_threshold,
            )
            result = refinement.final_output
            result["refinement_metadata"] = {
                "passes_completed": refinement.passes_completed,
                "final_score": refinement.final_grade.overall_score,
                "improved_from_initial": refinement.improved,
            }

        concepts = result.get("concepts", [])
        sources_used = set(c.get("source", "unknown") for c in concepts)

        quality_warnings: list[str] = []
        if len(sources_used) < 3:
            quality_warnings.append(
                f"Only {len(sources_used)} concept sources used — need at least 3 "
                f"(copy-derived, reptile, audience, wild)"
            )
        if len(concepts) < 15:
            quality_warnings.append(f"Only {len(concepts)} concepts generated — target is 30-50")

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "image_concepts": result,
                "concept_count": len(concepts),
                "sources_used": list(sources_used),
            },
            quality_warnings=quality_warnings,
        )

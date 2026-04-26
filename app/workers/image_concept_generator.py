"""Image Concept Generator — generates 30-50 visual concepts from multiple sources.

Input:  Finished ad copy
Output: Raw image concepts ranked by scroll-stop potential
Banks:  recall from CREATIVE, VOC, OFFER
Sources: Copy-derived, reptile triggers, audience language, wild associations

Uses 10-pass refinement with per-weakness targeted context recall to push
concepts beyond generic stock-photo ideas toward scroll-stopping imagery.
"""

from __future__ import annotations

import json
import logging

from app.knowledge.base_training import get_training_context
from app.prompts.systems import IMAGE_CONCEPT_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.intelligence.refinement_engine import IMAGE_CONCEPT_CRITERIA, refinement_engine
from app.services.llm.router import Capability, router
from app.services.llm.schemas import IMAGE_CONCEPT_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


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
        system_prompt = f"{IMAGE_CONCEPT_GENERATOR_SYSTEM}\n\n{training_context}"
        user_prompt = (
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
        )

        # Initial generation using CONCEPT_GENERATION capability
        initial = await router.generate(
            capability=Capability.CONCEPT_GENERATION,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
            max_tokens=8000,
            json_schema=IMAGE_CONCEPT_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        if initial.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # 10-pass refinement with per-weakness targeted context
        async def _weakness_resolver(weaknesses: list[str]) -> str:
            from app.services.intelligence.weakness_context_map import (
                get_top_weakness_context,
            )
            return await get_top_weakness_context(
                weaknesses, account_id, offer_id,
            )

        full_context = f"AD COPY:\n{ad_copy[:2000]}\n\nEVIDENCE:\n{evidence_text[:3000]}"
        refined = await refinement_engine.refine(
            task_type="image_concept_generation",
            initial_output=initial,
            system_prompt=system_prompt,
            context=full_context,
            max_passes=10,
            threshold=7.5,
            criteria=IMAGE_CONCEPT_CRITERIA,
            weakness_context_resolver=_weakness_resolver,
        )

        logger.info(
            "image_concept_generator.refined passes=%d score=%.1f improved=%s",
            refined.passes_completed, refined.final_grade.overall_score,
            refined.improved,
        )

        result = refined.final_output
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
                "refinement_passes": refined.passes_completed,
                "refinement_score": refined.final_grade.overall_score,
                "grade_trajectory": [
                    {"pass": g.pass_number, "score": g.overall_score}
                    for g in refined.all_grades
                ],
            },
            quality_warnings=quality_warnings,
        )

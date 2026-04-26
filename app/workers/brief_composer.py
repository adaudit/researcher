"""Brief Composer Worker — LLM-powered strategic brief assembly.

Input:  Approved seeds and strategic maps
Output: Strategic briefs with mechanism bridges
Banks:  recall from approved banks and outputs
Guard:  Must include mechanism bridge
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.prompts.systems import BRIEF_COMPOSER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.knowledge.base_training import get_training_context
from app.services.intelligence.refinement_engine import COPY_CRITERIA, refinement_engine
from app.services.llm.router import Capability, router
from app.services.llm.schemas import BRIEF_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

BRIEF_CRITERIA = [
    c for c in COPY_CRITERIA
    if c.name in ("mechanism_bridge", "proof_density", "anti_generic", "hook_strength")
]


class BriefComposerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="brief_composer",
        purpose="Compose strategic briefs from approved seeds and strategy maps",
        accepted_input_types=["strategy_map", "seed_bank", "approved_outputs"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_strategy_context",
            "assemble_all_strategic_inputs",
            "llm_compose_briefs",
            "validate_mechanism_bridge",
            "anti_generic_check",
        ],
        quality_checks=[
            "brief_must_include_mechanism_bridge",
            "proof_sequence_must_follow_belief_transfer_logic",
            "hook_must_connect_to_desire_evidence",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        memories = await recall_for_worker(
            "brief_composer",
            account_id,
            "mechanism proof hook desire CTA offer brief strategy winning creative",
            offer_id=offer_id,
            top_k=30,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Assemble upstream strategy outputs
        strategy_context = ""
        for key in ("desire_map", "proof_inventory", "differentiation_map",
                     "hook_territory_map", "strategy_map"):
            data = params.get(key)
            if data:
                strategy_context += f"\n## {key.replace('_', ' ').title()}\n{json.dumps(data, indent=1, default=str)[:2000]}\n"

        seeds = params.get("seeds", [])
        seed_text = json.dumps(seeds, indent=1, default=str) if seeds else "No specific seeds — generate from evidence."

        training_context = get_training_context()
        system_prompt = f"{BRIEF_COMPOSER_SYSTEM}\n\n{training_context}"
        full_context = (
            f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n\n"
            f"STRATEGY CONTEXT:\n{strategy_context}\n\n"
            f"SEEDS:\n{seed_text}"
        )

        # Initial generation
        initial = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=system_prompt,
            user_prompt=(
                f"Compose strategic briefs using the following inputs.\n\n"
                f"{full_context}\n\n"
                f"Create 3-5 briefs targeting different awareness levels. "
                f"Each MUST have a mechanism bridge and anti-generic rules."
            ),
            temperature=0.4,
            max_tokens=8000,
            json_schema=BRIEF_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        # 10-pass refinement with per-weakness targeted context
        async def _weakness_resolver(weaknesses: list[str]) -> str:
            from app.services.intelligence.weakness_context_map import (
                get_top_weakness_context,
            )
            return await get_top_weakness_context(
                weaknesses, account_id, offer_id,
            )

        refined = await refinement_engine.refine(
            task_type="copy_generation",
            initial_output=initial,
            system_prompt=system_prompt,
            context=full_context[:5000],
            max_passes=10,
            threshold=7.5,
            criteria=BRIEF_CRITERIA,
            weakness_context_resolver=_weakness_resolver,
        )

        logger.info(
            "brief_composer.refined passes=%d score=%.1f improved=%s",
            refined.passes_completed, refined.final_grade.overall_score,
            refined.improved,
        )

        analysis = refined.final_output
        quality_warnings: list[str] = []
        for brief in analysis.get("briefs", []):
            if not brief.get("mechanism_bridge"):
                quality_warnings.append(
                    f"Brief '{brief.get('brief_id', '?')}' missing mechanism bridge"
                )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={
                "brief_pack": analysis,
                "refinement_passes": refined.passes_completed,
                "refinement_score": refined.final_grade.overall_score,
                "grade_trajectory": [
                    {"pass": g.pass_number, "score": g.overall_score}
                    for g in refined.all_grades
                ],
            },
            quality_warnings=quality_warnings,
        )

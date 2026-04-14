"""Audience Psychology Worker — LLM-powered desire and motivation mapping.

Input:  Normalized evidence from recall
Output: Desire map, fear map, awareness map
Banks:  recall from offer, VOC, creative, reflection banks
Guard:  Must not exceed evidence coverage
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import AUDIENCE_PSYCHOLOGY_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.knowledge.base_training import get_training_context
from app.services.llm.router import Capability, router
from app.services.llm.schemas import DESIRE_MAP_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class AudiencePsychologyWorker(BaseWorker):
    contract = SkillContract(
        skill_name="audience_psychology",
        purpose="Map audience desires, fears, identity motives, and awareness levels from evidence",
        accepted_input_types=["evidence_set", "recall_query"],
        recall_scope=[BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_audience_evidence",
            "llm_synthesize_desire_map",
            "validate_evidence_coverage",
            "produce_desire_map",
        ],
        quality_checks=[
            "every_desire_must_cite_evidence",
            "fears_must_distinguish_stated_from_implied",
            "awareness_map_must_cover_spectrum",
            "must_not_exceed_evidence_coverage",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id

        # Recall broadly across audience-relevant banks
        memories = await recall_for_worker(
            "audience_psychology",
            account_id,
            "audience desires fears pain objections motivation identity language what they want",
            offer_id=offer_id,
            top_k=40,
        )

        if not memories:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No audience evidence available. Run VOC mining and offer analysis first."],
            )

        # Format evidence for LLM
        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # LLM synthesis — STRATEGIC_REASONING for deep psychological mapping
        training_context = get_training_context()
        analysis = await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=f"{AUDIENCE_PSYCHOLOGY_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Based on the following {len(memories)} pieces of evidence, "
                f"build a complete audience desire map.\n\n"
                f"Do NOT exceed the evidence. If a category has no evidence, say so.\n\n"
                f"EVIDENCE:\n{evidence_text}"
            ),
            temperature=0.3,
            max_tokens=6000,
            json_schema=DESIRE_MAP_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse desire map"],
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "desire_map": analysis,
                "evidence_count": len(memories),
            },
        )

"""Differentiation Worker — LLM-powered sameness and contrast mapping.

Input:  Offer map plus market context
Output: Consequence map and contrast points
Banks:  recall across offer, creative, research banks
Guard:  Comparison logic must be explicit
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import DIFFERENTIATION_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import DIFFERENTIATION_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class DifferentiationWorker(BaseWorker):
    contract = SkillContract(
        skill_name="differentiation",
        purpose="Map category sameness, identify contrasts, and build consequence framing",
        accepted_input_types=["offer_map", "market_context"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.RESEARCH],
        write_scope=[],
        steps=[
            "recall_offer_and_market_context",
            "llm_identify_sameness_and_contrasts",
            "llm_build_consequence_framing",
            "validate_comparison_logic",
        ],
        quality_checks=[
            "comparison_logic_must_be_explicit",
            "contrasts_must_reference_evidence",
            "consequences_must_be_logically_derived",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id

        memories = await recall_for_worker(
            "differentiation",
            account_id,
            "offer mechanism competitor comparison unique different alternative market category",
            offer_id=offer_id,
            top_k=30,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        analysis = await llm_client.generate(
            system_prompt=DIFFERENTIATION_SYSTEM,
            user_prompt=(
                f"Analyze this offer's differentiation based on {len(memories)} evidence items.\n\n"
                f"Start with what's the SAME as everything else. "
                f"Then find genuine contrasts and build consequence framing.\n\n"
                f"EVIDENCE:\n{evidence_text}"
            ),
            tier=ModelTier.ADVANCED,
            temperature=0.3,
            max_tokens=5000,
            json_schema=DIFFERENTIATION_SCHEMA,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={"differentiation_map": analysis, "evidence_count": len(memories)},
        )

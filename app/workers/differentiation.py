"""Differentiation Worker

Input:  Offer map plus market context
Output: Consequence map and contrast points
Banks:  recall and reflect across offer, creative, research banks
Guard:  Comparison logic must be explicit
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
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
            "identify_category_sameness",
            "extract_unique_contrasts",
            "build_consequence_framing",
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
            "offer mechanism competitor comparison unique different alternative",
            offer_id=offer_id,
            top_k=25,
        )

        # Analyze for sameness and contrasts
        category_sameness: list[str] = []
        contrasts: list[dict[str, Any]] = []
        consequences: list[dict[str, Any]] = []

        for mem in memories:
            content = mem.get("content", "")
            if "competitive_signal" in mem.get("metadata", {}).get("evidence_type", ""):
                category_sameness.append(content)
            elif "mechanism" in mem.get("metadata", {}).get("evidence_type", ""):
                contrasts.append({
                    "point": content,
                    "evidence_ref": mem.get("id"),
                })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "differentiation_map": {
                    "category_sameness": category_sameness,
                    "contrasts": contrasts,
                    "consequence_framing": consequences,
                    "evidence_count": len(memories),
                }
            },
        )

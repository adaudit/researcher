"""Proof Inventory Worker

Input:  Claims, studies, testimonials, product facts
Output: Proof hierarchy and proof gaps
Banks:  recall and reflect across offer, page, research banks
Guard:  Unsupported proof is forbidden
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class ProofInventoryWorker(BaseWorker):
    contract = SkillContract(
        skill_name="proof_inventory",
        purpose="Build proof hierarchy from evidence and identify proof gaps",
        accepted_input_types=["claims_list", "evidence_set"],
        recall_scope=[BankType.OFFER, BankType.LANDING_PAGE, BankType.RESEARCH],
        write_scope=[],
        steps=[
            "recall_all_proof_elements",
            "classify_proof_types",
            "rank_proof_strength",
            "identify_proof_gaps",
            "build_proof_hierarchy",
        ],
        quality_checks=[
            "unsupported_proof_is_forbidden",
            "each_proof_must_have_source_citation",
            "proof_strength_ranking_must_be_justified",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id

        memories = await recall_for_worker(
            "proof_inventory",
            account_id,
            "proof evidence study clinical testimonial certification result statistic",
            offer_id=offer_id,
            top_k=30,
        )

        proof_items: list[dict[str, Any]] = []
        for mem in memories:
            content = mem.get("content", "")
            metadata = mem.get("metadata", {})
            proof_items.append({
                "statement": content,
                "proof_type": metadata.get("evidence_type", "general"),
                "source_url": metadata.get("source_url"),
                "confidence": metadata.get("confidence_score", 0.5),
                "memory_ref": mem.get("id"),
            })

        # Sort by confidence (strongest first)
        proof_items.sort(key=lambda x: x["confidence"], reverse=True)

        # Classify into hierarchy
        scientific = [p for p in proof_items if p["proof_type"] in ("research_finding", "scientific")]
        social = [p for p in proof_items if p["proof_type"] in ("testimonial", "social")]
        authority = [p for p in proof_items if p["proof_type"] in ("authority", "certification")]
        product = [p for p in proof_items if p["proof_type"] in ("product_fact", "mechanism_insight")]

        # Identify gaps
        gaps: list[str] = []
        if not scientific:
            gaps.append("No scientific/clinical proof found")
        if not social:
            gaps.append("No social proof or testimonials found")
        if not authority:
            gaps.append("No authority proof found")

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "proof_hierarchy": {
                    "scientific": scientific,
                    "social": social,
                    "authority": authority,
                    "product": product,
                },
                "total_proof_items": len(proof_items),
                "proof_gaps": gaps,
            },
        )

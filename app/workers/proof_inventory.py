"""Proof Inventory Worker — LLM-powered proof hierarchy and gap analysis.

Input:  Claims, studies, testimonials, product facts
Output: Proof hierarchy and proof gaps
Banks:  recall across offer, page, research banks
Guard:  Unsupported proof is forbidden
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import PROOF_INVENTORY_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.knowledge.base_training import get_training_context
from app.services.llm.router import Capability, router
from app.services.llm.schemas import PROOF_INVENTORY_SCHEMA
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
            "llm_classify_and_rank_proof",
            "llm_identify_gaps",
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
            "proof evidence study clinical testimonial certification result statistic claim",
            offer_id=offer_id,
            top_k=40,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        training_context = get_training_context()
        analysis = await router.generate(
            capability=Capability.SYNTHESIS,
            system_prompt=f"{PROOF_INVENTORY_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Build the complete proof hierarchy from these {len(memories)} evidence items.\n\n"
                f"Rank each proof element by type and strength. Identify all gaps.\n\n"
                f"EVIDENCE:\n{evidence_text}"
            ),
            temperature=0.2,
            max_tokens=6000,
            json_schema=PROOF_INVENTORY_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        requires_review = False
        quality_warnings: list[str] = []
        gaps = analysis.get("proof_gaps", [])
        if gaps:
            quality_warnings.append(f"{len(gaps)} proof gap(s) identified")
            if any(g.get("impact") == "high" for g in gaps):
                requires_review = True

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={"proof_inventory": analysis, "evidence_count": len(memories)},
            quality_warnings=quality_warnings,
            requires_review=requires_review,
        )

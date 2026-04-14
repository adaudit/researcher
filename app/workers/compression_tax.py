"""Compression Tax Worker — LLM-powered draft compression with rationale ledger.

Input:  Near-final draft
Output: Reduction plan, revised draft, and rationale ledger
Banks:  recall offer and proof map
Guard:  Can only preserve extra text if it adds strategic value
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import COMPRESSION_TAX_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.knowledge.base_training import get_training_context
from app.services.llm.router import Capability, router
from app.services.llm.schemas import COMPRESSION_TAX_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CompressionTaxWorker(BaseWorker):
    contract = SkillContract(
        skill_name="compression_tax",
        purpose="Apply compression tax: cut non-strategic text, preserve proof and mechanism",
        accepted_input_types=["near_final_draft"],
        recall_scope=[BankType.OFFER],
        write_scope=[],
        steps=[
            "recall_offer_and_proof_context",
            "llm_segment_and_classify",
            "llm_apply_compression_rules",
            "build_rationale_ledger",
        ],
        quality_checks=[
            "proof_artifacts_must_be_preserved",
            "correction_examples_must_be_preserved",
            "threshold_lines_must_be_preserved",
            "strategic_story_elements_must_be_preserved",
            "generic_filler_must_be_compressed",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        draft_text = params.get("draft_text", "")
        if not draft_text:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No draft text provided"],
            )

        # Recall offer context for classification
        offer_context = await recall_for_worker(
            "compression_tax",
            account_id,
            "mechanism proof CTA offer specific evidence",
            offer_id=offer_id,
            top_k=10,
        )

        context_text = "\n".join(
            f"- {m.get('content', '')}" for m in offer_context
        ) if offer_context else "No offer context available."

        original_word_count = len(draft_text.split())

        training_context = get_training_context()
        analysis = await router.generate(
            capability=Capability.COPY_ANALYSIS,
            system_prompt=f"{COMPRESSION_TAX_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Apply the compression tax to this draft ({original_word_count} words). "
                f"Target: cut 5-10% of non-offer text.\n\n"
                f"OFFER CONTEXT (what must be preserved):\n{context_text}\n\n"
                f"DRAFT:\n{draft_text}"
            ),
            temperature=0.1,
            max_tokens=8000,
            json_schema=COMPRESSION_TAX_SCHEMA,
            context_documents=[draft_text] if len(draft_text) > 3000 else None,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse compression analysis"],
            )

        # Reconstruct revised draft from blocks
        revised_blocks = [
            b.get("revised_text", b.get("original_text", ""))
            for b in analysis.get("blocks", [])
            if b.get("action") != "delete"
        ]
        revised_draft = "\n\n".join(revised_blocks)
        revised_word_count = len(revised_draft.split())

        analysis["revised_draft"] = revised_draft
        analysis["original_word_count"] = original_word_count
        analysis["revised_word_count"] = revised_word_count
        analysis["reduction_percentage"] = round(
            (1 - revised_word_count / max(original_word_count, 1)) * 100, 1
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"compression_result": analysis},
        )

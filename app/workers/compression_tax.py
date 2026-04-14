"""Compression Tax Worker

Input:  Near-final draft
Output: Reduction plan and rationale ledger
Banks:  recall offer and proof map
Guard:  Can only preserve extra text if it adds strategic value

Rule: Cut 5-10% of non-offer text unless the added text contributes a
proof artifact, correction example, threshold line, or story element.
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
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
            "segment_draft_into_blocks",
            "classify_each_block_role",
            "apply_compression_rules",
            "generate_reduction_plan",
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

        # Segment and classify
        paragraphs = [p.strip() for p in draft_text.split("\n\n") if p.strip()]
        original_word_count = len(draft_text.split())

        ledger: list[dict[str, Any]] = []
        preserved: list[str] = []
        removed: list[str] = []

        for para in paragraphs:
            role = _classify_block_role(para)
            if role in ("proof_artifact", "correction_example", "threshold_line", "story_element", "mechanism", "cta"):
                preserved.append(para)
                ledger.append({"text": para[:100], "role": role, "action": "preserve", "reason": f"Contains {role}"})
            elif role == "generic_filler":
                removed.append(para)
                ledger.append({"text": para[:100], "role": role, "action": "remove", "reason": "Generic filler with no strategic value"})
            else:
                preserved.append(para)
                ledger.append({"text": para[:100], "role": role, "action": "preserve", "reason": "Kept pending review"})

        revised_text = "\n\n".join(preserved)
        revised_word_count = len(revised_text.split())
        reduction_pct = round((1 - revised_word_count / max(original_word_count, 1)) * 100, 1)

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "revised_draft": revised_text,
                "original_word_count": original_word_count,
                "revised_word_count": revised_word_count,
                "reduction_percentage": reduction_pct,
                "rationale_ledger": ledger,
                "removed_blocks": len(removed),
                "preserved_blocks": len(preserved),
            },
        )


def _classify_block_role(text: str) -> str:
    text_lower = text.lower()

    proof_signals = ["study", "clinical", "proven", "research", "published", "%",
                     "customers", "testimonial", "certified", "doctor"]
    if any(s in text_lower for s in proof_signals):
        return "proof_artifact"

    mechanism_signals = ["works by", "mechanism", "how it works", "the reason",
                         "because", "what makes"]
    if any(s in text_lower for s in mechanism_signals):
        return "mechanism"

    cta_signals = ["order now", "buy now", "get started", "try", "click", "add to cart",
                   "sign up", "subscribe"]
    if any(s in text_lower for s in cta_signals):
        return "cta"

    correction_signals = ["unlike", "instead of", "not like", "the problem with",
                          "most people think", "the truth is"]
    if any(s in text_lower for s in correction_signals):
        return "correction_example"

    threshold_signals = ["what if", "imagine", "picture this", "there's a moment"]
    if any(s in text_lower for s in threshold_signals):
        return "threshold_line"

    # Check for generic filler
    generic_signals = ["in today's", "in conclusion", "furthermore", "moreover",
                       "it goes without saying", "it's no secret", "at the end of the day"]
    if any(s in text_lower for s in generic_signals):
        return "generic_filler"

    # Short connective text is likely filler
    if len(text.split()) < 15:
        return "connective"

    return "body_text"

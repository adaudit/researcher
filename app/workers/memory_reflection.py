"""Memory Reflection Worker — LLM-powered durable lesson generation.

Input:  Completed cycles and results
Output: Durable lessons, emerging patterns, strategic shifts
Banks:  reflect into reflection bank
Guard:  Cannot promote weak hypotheses into durable memory
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import MEMORY_REFLECTION_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, trigger_reflection
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import REFLECTION_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class MemoryReflectionWorker(BaseWorker):
    contract = SkillContract(
        skill_name="memory_reflection",
        purpose="Generate durable lessons and mental models from accumulated evidence and outcomes",
        accepted_input_types=["completed_cycles", "outcome_data", "reflection_trigger"],
        recall_scope=[
            BankType.OFFER, BankType.CREATIVE, BankType.VOC,
            BankType.LANDING_PAGE, BankType.RESEARCH,
        ],
        write_scope=[BankType.REFLECTION],
        requires_approval=True,
        steps=[
            "recall_broad_evidence",
            "llm_identify_patterns_and_lessons",
            "filter_weak_hypotheses",
            "trigger_hindsight_reflection",
        ],
        quality_checks=[
            "weak_hypotheses_cannot_become_durable_memory",
            "lessons_must_cite_multiple_evidence_sources",
            "mental_models_must_be_falsifiable",
            "reflection_must_not_contradict_approved_truths",
        ],
        escalation_rule="All reflection outputs require review before promotion to durable memory",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Broad recall for reflection
        memories = await recall_for_worker(
            "memory_reflection",
            account_id,
            "pattern trend lesson outcome result observation recurring evidence proof change",
            offer_id=offer_id,
            top_k=60,
        )

        if not memories:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Insufficient evidence for reflection. Accumulate more observations first."],
            )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # LLM reflection — ADVANCED tier for highest-quality strategic reasoning
        analysis = await llm_client.generate(
            system_prompt=MEMORY_REFLECTION_SYSTEM,
            user_prompt=(
                f"Reflect on these {len(memories)} evidence items. "
                f"Identify durable lessons, emerging patterns, and strategic shifts.\n\n"
                f"Remember: only promote to 'durable lesson' if supported by MULTIPLE "
                f"INDEPENDENT sources. Include a falsifiable prediction for each lesson.\n\n"
                f"EVIDENCE:\n{evidence_text}"
            ),
            tier=ModelTier.ADVANCED,
            temperature=0.3,
            max_tokens=6000,
            json_schema=REFLECTION_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 4000 else None,
        )

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse reflection output"],
            )

        # Also trigger Hindsight's native reflection for complementary insights
        source_banks = [
            BankType.OFFER, BankType.CREATIVE, BankType.VOC,
            BankType.LANDING_PAGE, BankType.RESEARCH,
        ]

        try:
            hindsight_reflection = await trigger_reflection(
                account_id=account_id,
                source_bank_types=source_banks,
                offer_id=offer_id,
                prompt=params.get("reflection_prompt", (
                    "Identify the most important recurring patterns and "
                    "durable strategic lessons from the accumulated evidence."
                )),
            )
            analysis["hindsight_reflection_id"] = hindsight_reflection.get("id")
        except Exception:
            pass  # Hindsight reflection is supplementary

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "reflection": analysis,
                "evidence_analyzed": len(memories),
            },
            requires_review=True,
        )

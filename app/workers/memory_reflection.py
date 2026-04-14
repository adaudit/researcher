"""Memory Reflection Worker

Input:  Completed cycles and results
Output: Durable lessons and mental models
Banks:  reflect into reflection bank
Guard:  Cannot promote weak hypotheses into durable memory
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, trigger_reflection
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
            "recall_recent_evidence",
            "identify_recurring_patterns",
            "evaluate_hypothesis_strength",
            "generate_candidate_lessons",
            "score_lesson_confidence",
            "filter_weak_hypotheses",
            "submit_for_reflection",
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

        # Recall broadly for reflection
        memories = await recall_for_worker(
            "memory_reflection",
            account_id,
            "pattern trend lesson outcome result observation recurring",
            offer_id=offer_id,
            top_k=50,
        )

        # Trigger Hindsight reflection
        reflection_prompt = params.get("reflection_prompt", (
            "Analyze accumulated evidence and outcomes. Identify recurring patterns, "
            "emerging rules, and durable lessons. Only promote insights that are "
            "supported by multiple independent evidence sources."
        ))

        source_banks = [
            BankType.OFFER, BankType.CREATIVE, BankType.VOC,
            BankType.LANDING_PAGE, BankType.RESEARCH,
        ]

        reflection_result = await trigger_reflection(
            account_id=account_id,
            source_bank_types=source_banks,
            offer_id=offer_id,
            prompt=reflection_prompt,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "reflection_id": reflection_result.get("id"),
                "insights": reflection_result.get("insights", []),
                "evidence_analyzed": len(memories),
            },
            requires_review=True,  # Always require review for reflections
        )

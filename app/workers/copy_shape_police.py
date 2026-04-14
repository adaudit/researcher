"""Copy Shape Police Worker — LLM-powered anti-generic enforcement.

Input:  Draft copy plus strategy
Output: Flagged generic patterns and rewrite directions
Banks:  recall approved strategic outputs
Guard:  Must enforce anti-generic policy
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import COPY_SHAPE_POLICE_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import COPY_REVIEW_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CopyShapePoliceWorker(BaseWorker):
    contract = SkillContract(
        skill_name="copy_shape_police",
        purpose="Detect and flag generic patterns in draft copy, enforce anti-generic policy",
        accepted_input_types=["draft_copy", "strategy_reference"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE],
        write_scope=[],
        steps=[
            "recall_strategy_context",
            "llm_analyze_copy_quality",
            "flag_generic_patterns",
            "generate_rewrite_directions",
        ],
        quality_checks=[
            "must_enforce_anti_generic_policy",
            "flagged_patterns_must_include_rewrite_directions",
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

        # Recall strategy for evidence-based rewrite suggestions
        strategy_context = await recall_for_worker(
            "copy_shape_police",
            account_id,
            "mechanism proof specific language evidence offer unique",
            offer_id=offer_id,
            top_k=15,
        )

        strategy_text = "\n".join(
            f"- {m.get('content', '')}" for m in strategy_context
        ) if strategy_context else "No strategy context available."

        analysis = await llm_client.generate(
            system_prompt=COPY_SHAPE_POLICE_SYSTEM,
            user_prompt=(
                f"Review this draft copy for generic language, LLM-isms, and strategic gaps.\n\n"
                f"AVAILABLE STRATEGY CONTEXT (use for rewrite directions):\n{strategy_text}\n\n"
                f"DRAFT COPY:\n{draft_text}"
            ),
            tier=ModelTier.STANDARD,
            temperature=0.2,
            max_tokens=5000,
            json_schema=COPY_REVIEW_SCHEMA,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={"copy_review": analysis},
        )

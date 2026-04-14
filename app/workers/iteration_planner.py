"""Iteration Planner Worker — LLM-powered iteration target generation.

Input:  Performance feedback plus current strategy
Output: Iteration headers with test hypotheses
Banks:  recall and reflect across all relevant banks
Guard:  Every recommendation must tie to evidence or outcomes
"""

from __future__ import annotations

import json
from typing import Any

from app.prompts.systems import ITERATION_PLANNER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import ITERATION_HEADER_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class IterationPlannerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="iteration_planner",
        purpose="Generate iteration headers and next-test hypotheses from evidence and outcomes",
        accepted_input_types=["performance_feedback", "strategy_map", "evidence_set"],
        recall_scope=[
            BankType.OFFER, BankType.VOC, BankType.CREATIVE,
            BankType.LANDING_PAGE, BankType.RESEARCH, BankType.REFLECTION,
        ],
        write_scope=[],
        steps=[
            "recall_current_strategy_state",
            "assemble_performance_and_evidence",
            "llm_generate_iteration_targets",
            "validate_evidence_backing",
        ],
        quality_checks=[
            "every_recommendation_must_cite_evidence_or_outcome",
            "iteration_targets_must_be_actionable",
            "constraints_must_be_explicitly_stated",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        performance = params.get("performance_feedback", {})
        current_strategy = params.get("strategy_map", {})

        # Broad recall across all relevant banks
        memories = await recall_for_worker(
            "iteration_planner",
            account_id,
            "performance results outcomes improvement opportunity weakness strength proof hook mechanism",
            offer_id=offer_id,
            top_k=40,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        perf_text = json.dumps(performance, indent=1, default=str) if performance else "No performance data available yet."
        strategy_text = json.dumps(current_strategy, indent=1, default=str)[:3000] if current_strategy else "No current strategy map."

        analysis = await llm_client.generate(
            system_prompt=ITERATION_PLANNER_SYSTEM,
            user_prompt=(
                f"Generate iteration headers based on the following inputs.\n\n"
                f"PERFORMANCE DATA:\n{perf_text}\n\n"
                f"CURRENT STRATEGY:\n{strategy_text}\n\n"
                f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n\n"
                f"Create prioritized iteration targets. Each must have a test hypothesis."
            ),
            tier=ModelTier.ADVANCED,
            temperature=0.3,
            max_tokens=6000,
            json_schema=ITERATION_HEADER_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={
                "iteration_plan": analysis,
                "evidence_count": len(memories),
            },
        )

"""Iteration Planner Worker

Input:  Performance feedback plus current strategy
Output: Iteration headers and next hypotheses
Banks:  recall and reflect across all relevant banks
Guard:  Every recommendation must tie to evidence or outcomes
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
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
            "analyze_performance_feedback",
            "identify_underperforming_elements",
            "cross_reference_with_evidence",
            "generate_iteration_targets",
            "prioritize_by_impact",
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
            "performance results outcomes improvement opportunity weakness strength",
            offer_id=offer_id,
            top_k=30,
        )

        iteration_headers: list[dict[str, Any]] = []

        # Analyze performance signals
        metrics = performance.get("metrics", {})
        asset_type = performance.get("asset_type", "landing_page")

        # Generate targets based on gaps between performance and evidence
        if metrics.get("ctr", 0) < 0.02:
            iteration_headers.append({
                "asset_type": asset_type,
                "asset_section": "hook / headline",
                "target": "Strengthen hook with desire-led or consequence-led opener",
                "reason": f"CTR at {metrics.get('ctr', 0):.3f} suggests weak hook engagement",
                "evidence_refs": [m.get("id") for m in memories[:3]],
                "priority": "high",
                "expected_effect": "Improve click-through by anchoring in proven desire clusters",
                "constraint": "Maintain mechanism and CTA integrity",
            })

        if metrics.get("conversion_rate", 0) < 0.01:
            iteration_headers.append({
                "asset_type": asset_type,
                "asset_section": "proof section + CTA",
                "target": "Strengthen belief transfer chain before CTA",
                "reason": f"Conversion at {metrics.get('conversion_rate', 0):.3f} suggests proof gap",
                "evidence_refs": [m.get("id") for m in memories[:3]],
                "priority": "high",
                "expected_effect": "Improve conversion by closing proof gaps",
                "constraint": "Do not change offer or pricing",
            })

        if metrics.get("bounce_rate", 0) > 0.7:
            iteration_headers.append({
                "asset_type": asset_type,
                "asset_section": "hero + above-fold",
                "target": "Reduce friction and strengthen relevance signal above fold",
                "reason": f"Bounce rate at {metrics.get('bounce_rate', 0):.1%} indicates poor initial relevance",
                "evidence_refs": [m.get("id") for m in memories[:3]],
                "priority": "critical",
                "expected_effect": "Reduce bounce rate through stronger problem-solution matching",
            })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "iteration_headers": iteration_headers,
                "header_count": len(iteration_headers),
                "evidence_used": len(memories),
                "performance_signals_analyzed": len(metrics),
            },
        )

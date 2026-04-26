"""Coverage Matrix Worker — maps creative diversity gaps.

Input:  All seeds, briefs, and performance data
Output: Coverage map across Segments × Awareness × CASH with gap report
Banks:  recall from SEEDS, CREATIVE, OFFER, REFLECTION
Guard:  Must identify clustering and gaps, not just list what exists
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.prompts.systems import COVERAGE_MATRIX_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.router import Capability, router
from app.services.llm.schemas import COVERAGE_MATRIX_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CoverageMatrixWorker(BaseWorker):
    contract = SkillContract(
        skill_name="coverage_matrix",
        purpose="Map creative coverage across Segments × Awareness × CASH and identify gaps",
        accepted_input_types=["seeds", "briefs", "performance_data"],
        recall_scope=[BankType.SEEDS, BankType.CREATIVE, BankType.OFFER, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_all_creative_assets",
            "recall_seeds_and_briefs",
            "llm_map_coverage",
            "identify_gaps_and_clustering",
            "prioritize_recommendations",
        ],
        quality_checks=[
            "all_three_dimensions_must_be_mapped",
            "gaps_must_be_specific_and_actionable",
            "recommendations_must_address_highest_severity_gaps",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall seeds
        seed_memories = await recall_for_worker(
            "coverage_matrix",
            account_id,
            "seed ideation hook angle format concept creative brief",
            offer_id=offer_id,
            top_k=50,
        )

        seeds_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in seed_memories
        )

        # Recall creative assets (ads, briefs, copy)
        creative_memories = await recall_for_worker(
            "coverage_matrix",
            account_id,
            "ad creative winning copy brief draft headline hook audience awareness",
            offer_id=offer_id,
            top_k=50,
        )

        creative_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in creative_memories
        )

        # Include performance data if provided
        performance = params.get("performance_data", {})
        perf_text = json.dumps(performance, indent=1, default=str)[:3000] if performance else "No performance data."

        # Include any explicitly passed briefs/seeds
        explicit_briefs = params.get("briefs", [])
        explicit_seeds = params.get("seeds", [])
        explicit_text = ""
        if explicit_briefs:
            explicit_text += f"\nEXPLICIT BRIEFS:\n{json.dumps(explicit_briefs, indent=1, default=str)[:3000]}\n"
        if explicit_seeds:
            explicit_text += f"\nEXPLICIT SEEDS:\n{json.dumps(explicit_seeds, indent=1, default=str)[:3000]}\n"

        training_context = get_training_context()
        result = await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=f"{COVERAGE_MATRIX_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Map the creative coverage matrix for this account.\n\n"
                f"SEEDS ({len(seed_memories)} recalled):\n{seeds_text}\n\n"
                f"CREATIVE ASSETS ({len(creative_memories)} recalled):\n{creative_text}\n\n"
                f"PERFORMANCE DATA:\n{perf_text}\n"
                f"{explicit_text}\n"
                f"Map coverage across Segments × Awareness Levels × CASH. "
                f"Identify clustering (where are we doing Battleship wrong?). "
                f"Identify gaps. Prioritize the 3-5 most impactful gaps to fill."
            ),
            temperature=0.3,
            max_tokens=6000,
            json_schema=COVERAGE_MATRIX_SCHEMA,
            context_documents=[seeds_text, creative_text] if len(seeds_text) + len(creative_text) > 5000 else None,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "coverage_matrix": result,
                "seeds_analyzed": len(seed_memories),
                "creative_analyzed": len(creative_memories),
            },
        )

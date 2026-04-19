"""Creative Loopback Worker — extracts winning vectors from top performers.

Input:  Performance data referencing winning ad images
Output: Winning vectors + expanded concept variations → SEEDS bank
Banks:  recall from CREATIVE, write to SEEDS
Guard:  Variations must test genuinely different hypotheses
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.prompts.systems import CREATIVE_LOOPBACK_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


LOOPBACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "winning_vectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "asset_ref": {"type": "string"},
                    "subject_matter": {"type": "string"},
                    "camera_angle": {"type": "string"},
                    "lighting": {"type": "string"},
                    "mood_emotion": {"type": "string"},
                    "color_palette": {"type": "string"},
                    "composition": {"type": "string"},
                    "native_quality": {"type": "string"},
                    "performance_signal": {"type": "string"},
                },
            },
        },
        "expanded_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "derived_from": {"type": "string"},
                    "vectors_preserved": {"type": "array", "items": {"type": "string"}},
                    "vectors_varied": {"type": "array", "items": {"type": "string"}},
                    "hypothesis": {"type": "string"},
                },
            },
        },
    },
}


class CreativeLoopbackWorker(BaseWorker):
    contract = SkillContract(
        skill_name="creative_loopback",
        purpose="Extract winning visual vectors from top performers and generate expanded variations",
        accepted_input_types=["performance_data", "winning_creatives"],
        recall_scope=[BankType.CREATIVE, BankType.SEEDS],
        write_scope=[BankType.SEEDS],
        steps=[
            "recall_top_performing_creatives",
            "llm_extract_winning_vectors",
            "llm_generate_expanded_variations",
            "retain_to_seeds_bank",
        ],
        quality_checks=[
            "vectors_must_be_specific_not_vague",
            "variations_must_test_different_hypotheses",
            "performance_signal_must_be_cited",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall top-performing creative assets
        memories = await recall_for_worker(
            "creative_loopback",
            account_id,
            "winning creative ad top performing image visual concept format",
            offer_id=offer_id,
            top_k=20,
        )

        creative_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Include explicit winning creative data
        winning_creatives = params.get("winning_creatives", [])
        performance_data = params.get("performance_data", {})

        explicit_text = ""
        if winning_creatives:
            explicit_text += f"\nWINNING CREATIVES:\n{json.dumps(winning_creatives, indent=1, default=str)[:5000]}\n"
        if performance_data:
            explicit_text += f"\nPERFORMANCE DATA:\n{json.dumps(performance_data, indent=1, default=str)[:3000]}\n"

        if not memories and not winning_creatives:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No winning creatives to analyze — provide performance data or winning_creatives"],
            )

        training_context = get_training_context(include_examples=False)
        result = await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=f"{CREATIVE_LOOPBACK_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Analyze top-performing creatives and generate expanded variations.\n\n"
                f"RECALLED CREATIVE ASSETS ({len(memories)} items):\n{creative_text}\n"
                f"{explicit_text}\n"
                f"1. Extract specific WINNING VECTORS from each winner.\n"
                f"2. Generate 10-15 expanded concept variations that PRESERVE winning vectors "
                f"while VARYING other elements.\n"
                f"3. Each variation must test a genuinely different hypothesis."
            ),
            temperature=0.5,
            max_tokens=6000,
            json_schema=LOOPBACK_SCHEMA,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Retain expanded concepts to SEEDS bank
        observations: list[dict[str, Any]] = []
        for concept in result.get("expanded_concepts", []):
            seed_content = (
                f"Seed (loopback): {concept.get('concept', '')}. "
                f"Derived from: {concept.get('derived_from', '')}. "
                f"Preserved: {', '.join(concept.get('vectors_preserved', []))}. "
                f"Hypothesis: {concept.get('hypothesis', '')}."
            )
            mem_result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.SEEDS,
                content=seed_content,
                offer_id=offer_id,
                source_type="loopback",
                evidence_type="ideation_seed",
                confidence_score=0.75,
                extra_metadata={"seed_source": "loopback"},
            )
            if mem_result:
                observations.append({"type": "seed", "memory_ref": mem_result.get("id")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "loopback_analysis": result,
                "winning_vectors": len(result.get("winning_vectors", [])),
                "expanded_concepts": len(result.get("expanded_concepts", [])),
            },
            observations=observations,
        )

"""Brief Composer Worker

Input:  Approved seeds and strategic maps
Output: Strategic briefs
Banks:  recall from approved banks and outputs
Guard:  Must include mechanism bridge
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class BriefComposerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="brief_composer",
        purpose="Compose strategic briefs from approved seeds and strategy maps",
        accepted_input_types=["strategy_map", "seed_bank", "approved_outputs"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_strategy_context",
            "select_seed_combinations",
            "build_hook_to_mechanism_bridge",
            "structure_proof_sequence",
            "compose_brief_sections",
            "validate_mechanism_bridge",
        ],
        quality_checks=[
            "brief_must_include_mechanism_bridge",
            "proof_sequence_must_follow_belief_transfer_logic",
            "hook_must_connect_to_desire_evidence",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        memories = await recall_for_worker(
            "brief_composer",
            account_id,
            "mechanism proof hook desire CTA offer brief",
            offer_id=offer_id,
            top_k=20,
        )

        strategy_map = params.get("strategy_map", {})
        seeds = params.get("seeds", [])

        briefs: list[dict[str, Any]] = []
        for seed in seeds:
            brief = {
                "seed_id": seed.get("id"),
                "hook": seed.get("hook", ""),
                "angle": seed.get("angle", ""),
                "awareness_level": seed.get("awareness_level", "solution_aware"),
                "mechanism_bridge": _build_mechanism_bridge(strategy_map),
                "proof_sequence": _build_proof_sequence(strategy_map),
                "cta": strategy_map.get("cta", ""),
                "evidence_refs": [m.get("id") for m in memories[:5]],
            }
            briefs.append(brief)

        quality_warnings: list[str] = []
        for brief in briefs:
            if not brief["mechanism_bridge"]:
                quality_warnings.append(f"Brief {brief['seed_id']} missing mechanism bridge")

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"briefs": briefs, "brief_count": len(briefs)},
            quality_warnings=quality_warnings,
        )


def _build_mechanism_bridge(strategy_map: dict) -> str:
    mechanism = strategy_map.get("mechanism", "")
    if mechanism:
        return f"Bridge to mechanism: {mechanism}"
    return ""


def _build_proof_sequence(strategy_map: dict) -> list[str]:
    proof = strategy_map.get("proof_hierarchy", {})
    sequence: list[str] = []
    for category in ("scientific", "authority", "social", "product"):
        items = proof.get(category, [])
        if items:
            sequence.append(f"{category}: {items[0].get('statement', '')}" if isinstance(items[0], dict) else f"{category}: {items[0]}")
    return sequence

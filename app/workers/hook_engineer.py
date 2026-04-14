"""Hook Engineer Worker

Input:  Desire map, awareness map, proof inventory
Output: Hook territories and examples
Banks:  recall from offer, VOC, creative, reflection banks
Guard:  Awareness level must be explicit
"""

from __future__ import annotations

from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class HookEngineerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="hook_engineer",
        purpose="Design hook territories segmented by awareness level and desire cluster",
        accepted_input_types=["desire_map", "awareness_map", "proof_inventory"],
        recall_scope=[BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_winning_hooks",
            "recall_desire_clusters",
            "recall_proof_elements",
            "map_hooks_by_awareness_level",
            "generate_hook_territories",
            "validate_awareness_alignment",
        ],
        quality_checks=[
            "every_hook_must_state_awareness_level",
            "hooks_must_connect_to_desire_evidence",
            "no_generic_benefit_hooks_without_proof_anchor",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall hook-relevant memories
        memories = await recall_for_worker(
            "hook_engineer",
            account_id,
            "hook angle opening headline desire pain proof mechanism",
            offer_id=offer_id,
            top_k=30,
        )

        awareness_levels = ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]
        desire_map = params.get("desire_map", {})

        hook_territories: dict[str, list[dict[str, Any]]] = {level: [] for level in awareness_levels}

        # Extract existing winning hooks
        for mem in memories:
            content = mem.get("content", "")
            metadata = mem.get("metadata", {})
            if metadata.get("evidence_type") == "hook_pattern":
                # Assign to appropriate awareness level
                for level in awareness_levels:
                    hook_territories[level].append({
                        "hook": content,
                        "source": "winning_creative",
                        "evidence_ref": mem.get("id"),
                        "awareness_level": level,
                    })
                    break  # Assign to first level as default

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "hook_territory_map": hook_territories,
                "evidence_count": len(memories),
                "desires_used": len(desire_map.get("wants", [])),
            },
        )

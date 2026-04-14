"""Hook Engineer Worker — LLM-powered hook territory design.

Input:  Desire map, awareness map, proof inventory
Output: Hook territories organized by awareness level
Banks:  recall from offer, VOC, creative, reflection banks
Guard:  Awareness level must be explicit; no generic hooks
"""

from __future__ import annotations

from typing import Any

from app.prompts.systems import HOOK_ENGINEER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.knowledge.base_training import get_training_context
from app.services.llm.router import Capability, router
from app.services.llm.schemas import HOOK_TERRITORY_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class HookEngineerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="hook_engineer",
        purpose="Design hook territories segmented by awareness level and desire cluster",
        accepted_input_types=["desire_map", "awareness_map", "proof_inventory"],
        recall_scope=[BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        write_scope=[],
        steps=[
            "recall_strategic_context",
            "assemble_desire_and_proof_inputs",
            "llm_generate_hook_territories",
            "validate_awareness_alignment",
            "anti_generic_check",
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

        # Recall hook-relevant context
        memories = await recall_for_worker(
            "hook_engineer",
            account_id,
            "hook angle opening headline desire pain proof mechanism winning creative objection",
            offer_id=offer_id,
            top_k=40,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Include upstream strategy maps if available
        desire_map = params.get("desire_map", {})
        proof_inventory = params.get("proof_inventory", {})
        diff_map = params.get("differentiation_map", {})

        upstream_context = ""
        if desire_map:
            upstream_context += f"\nDESIRE MAP:\n{_format_dict(desire_map)}\n"
        if proof_inventory:
            upstream_context += f"\nPROOF INVENTORY:\n{_format_dict(proof_inventory)}\n"
        if diff_map:
            upstream_context += f"\nDIFFERENTIATION MAP:\n{_format_dict(diff_map)}\n"

        training_context = get_training_context()
        analysis = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=f"{HOOK_ENGINEER_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Design hook territories for this offer based on the evidence below.\n\n"
                f"Create hooks for ALL 5 awareness levels. "
                f"Each hook must have a proof anchor and mechanism connection.\n\n"
                f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n"
                f"{upstream_context}"
            ),
            temperature=0.5,  # Higher for creative output
            max_tokens=6000,
            json_schema=HOOK_TERRITORY_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={
                "hook_territory_map": analysis,
                "evidence_count": len(memories),
            },
        )


def _format_dict(d: dict) -> str:
    """Compact dict formatting for prompt inclusion."""
    import json
    return json.dumps(d, indent=1, default=str)[:3000]

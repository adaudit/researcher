"""Brief Composer Worker — LLM-powered strategic brief assembly.

Input:  Approved seeds and strategic maps
Output: Strategic briefs with mechanism bridges
Banks:  recall from approved banks and outputs
Guard:  Must include mechanism bridge
"""

from __future__ import annotations

import json
from typing import Any

from app.prompts.systems import BRIEF_COMPOSER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.client import ModelTier, llm_client
from app.services.llm.schemas import BRIEF_SCHEMA
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
            "assemble_all_strategic_inputs",
            "llm_compose_briefs",
            "validate_mechanism_bridge",
            "anti_generic_check",
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
            "mechanism proof hook desire CTA offer brief strategy winning creative",
            offer_id=offer_id,
            top_k=30,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Assemble upstream strategy outputs
        strategy_context = ""
        for key in ("desire_map", "proof_inventory", "differentiation_map",
                     "hook_territory_map", "strategy_map"):
            data = params.get(key)
            if data:
                strategy_context += f"\n## {key.replace('_', ' ').title()}\n{json.dumps(data, indent=1, default=str)[:2000]}\n"

        seeds = params.get("seeds", [])
        seed_text = json.dumps(seeds, indent=1, default=str) if seeds else "No specific seeds — generate from evidence."

        analysis = await llm_client.generate(
            system_prompt=BRIEF_COMPOSER_SYSTEM,
            user_prompt=(
                f"Compose strategic briefs using the following inputs.\n\n"
                f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n\n"
                f"STRATEGY CONTEXT:\n{strategy_context}\n\n"
                f"SEEDS:\n{seed_text}\n\n"
                f"Create 3-5 briefs targeting different awareness levels. "
                f"Each MUST have a mechanism bridge and anti-generic rules."
            ),
            tier=ModelTier.ADVANCED,
            temperature=0.4,
            max_tokens=8000,
            json_schema=BRIEF_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        quality_warnings: list[str] = []
        for brief in analysis.get("briefs", []):
            if not brief.get("mechanism_bridge"):
                quality_warnings.append(
                    f"Brief '{brief.get('brief_id', '?')}' missing mechanism bridge"
                )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=not analysis.get("_parse_error"),
            data={"brief_pack": analysis},
            quality_warnings=quality_warnings,
        )

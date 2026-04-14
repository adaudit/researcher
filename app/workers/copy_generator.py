"""Copy Generator Worker — LLM-powered ad copy writing.

Input:  Brief pack + ad primer
Output: 2-4 draft ad copies per brief
Banks:  recall from OFFER, CREATIVE, VOC, PRIMERS
Guard:  Mechanism bridge required; anti-generic enforced
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.primers import PrimerType, primer_store
from app.prompts.systems import COPY_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.services.llm.schemas import COPY_GENERATION_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class CopyGeneratorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="copy_generator",
        purpose="Generate 2-4 draft ad copies from a strategic brief, grounded in evidence and mechanism",
        accepted_input_types=["brief_pack", "ad_primer"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.VOC, BankType.PRIMERS],
        write_scope=[BankType.CREATIVE],
        steps=[
            "recall_offer_and_creative_context",
            "load_ad_primer",
            "llm_generate_drafts",
            "validate_mechanism_bridges",
            "anti_generic_check",
            "retain_drafts_to_creative_bank",
        ],
        quality_checks=[
            "every_draft_must_have_mechanism_bridge",
            "proof_must_be_woven_not_stacked",
            "no_generic_hooks",
            "awareness_level_must_match_brief",
        ],
        escalation_rule="Escalate if mechanism is unclear or no proof elements available",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall relevant context
        memories = await recall_for_worker(
            "copy_generator",
            account_id,
            "mechanism proof hook desire CTA offer winning ad copy creative objection audience",
            offer_id=offer_id,
            top_k=30,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Load ad primer if available
        primer_text = ""
        if offer_id:
            primer_content = await primer_store.get(account_id, offer_id, PrimerType.AD)
            if primer_content:
                primer_text = f"\n\n## Ad Primer\n{primer_content}"

        # Assemble brief input
        brief_pack = params.get("brief_pack", {})
        brief_text = json.dumps(brief_pack, indent=1, default=str) if brief_pack else "No brief provided."

        training_context = get_training_context()
        system_prompt = f"{COPY_GENERATOR_SYSTEM}\n\n{training_context}{primer_text}"

        result = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=system_prompt,
            user_prompt=(
                f"Write ad copy drafts based on the following brief and evidence.\n\n"
                f"BRIEF:\n{brief_text}\n\n"
                f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n\n"
                f"Generate 2-4 drafts exploring different angles from the brief. "
                f"Each MUST have a mechanism bridge and proof elements."
            ),
            temperature=0.6,
            max_tokens=8000,
            json_schema=COPY_GENERATION_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Retain drafts to CREATIVE bank
        observations: list[dict[str, Any]] = []
        for draft in result.get("drafts", []):
            draft_content = (
                f"Ad Draft ({draft.get('format', 'unknown')}): "
                f"Hook: {draft.get('hook', '')} | "
                f"Body: {draft.get('body', '')[:200]}... | "
                f"CTA: {draft.get('cta', '')} | "
                f"Mechanism: {draft.get('mechanism_bridge', '')}"
            )
            mem_result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.CREATIVE,
                content=draft_content,
                offer_id=offer_id,
                source_type="generated",
                evidence_type="ad_draft",
                confidence_score=0.7,
            )
            if mem_result:
                observations.append({
                    "type": "ad_draft",
                    "draft_id": draft.get("draft_id"),
                    "memory_ref": mem_result.get("id"),
                })

        quality_warnings: list[str] = []
        for draft in result.get("drafts", []):
            if not draft.get("mechanism_bridge"):
                quality_warnings.append(
                    f"Draft '{draft.get('draft_id', '?')}' missing mechanism bridge"
                )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={"copy_drafts": result},
            observations=observations,
            quality_warnings=quality_warnings,
        )

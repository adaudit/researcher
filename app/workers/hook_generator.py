"""Hook Generator Worker — high-volume hook generation with strength pass.

Input:  Brief + hook primer
Output: 10-20 hooks per brief, ranked with proof anchors
Banks:  recall from OFFER, VOC, CREATIVE, PRIMERS
Guard:  No generic hooks; every hook needs proof anchor
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.primers import PrimerType, primer_store
from app.prompts.systems import HOOK_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.router import Capability, router
from app.services.llm.schemas import HOOK_GENERATION_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class HookGeneratorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="hook_generator",
        purpose="Generate 10-20 hooks per brief with iterative strength pass",
        accepted_input_types=["brief_pack", "hook_primer"],
        recall_scope=[BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.PRIMERS],
        write_scope=[],
        steps=[
            "recall_hook_context",
            "load_hook_primer",
            "llm_generate_hooks",
            "llm_strength_pass",
            "rank_and_validate",
        ],
        quality_checks=[
            "every_hook_must_have_proof_anchor",
            "every_hook_must_have_mechanism_connection",
            "no_generic_benefit_hooks",
            "awareness_levels_must_be_diverse",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall hook-relevant context
        memories = await recall_for_worker(
            "hook_generator",
            account_id,
            "hook desire pain proof mechanism objection winning creative audience exact phrase",
            offer_id=offer_id,
            top_k=40,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Load hook primer if available
        primer_text = ""
        if offer_id:
            primer_content = await primer_store.get(account_id, offer_id, PrimerType.HOOK)
            if primer_content:
                primer_text = f"\n\n## Hook Primer\n{primer_content}"

        # Brief input
        brief_pack = params.get("brief_pack", {})
        brief_text = json.dumps(brief_pack, indent=1, default=str) if brief_pack else "No brief provided."

        training_context = get_training_context()
        system_prompt = f"{HOOK_GENERATOR_SYSTEM}\n\n{training_context}{primer_text}"

        # Step 1: Generate initial hooks
        result = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=system_prompt,
            user_prompt=(
                f"Generate 15-20 hooks based on the following brief and evidence.\n\n"
                f"BRIEF:\n{brief_text}\n\n"
                f"RECALLED EVIDENCE ({len(memories)} items):\n{evidence_text}\n\n"
                f"Cover ALL 5 awareness levels. Every hook needs a proof anchor "
                f"and mechanism connection. After generating, do a STRENGTH PASS "
                f"to make each hook more specific and powerful."
            ),
            temperature=0.7,
            max_tokens=6000,
            json_schema=HOOK_GENERATION_SCHEMA,
            context_documents=[evidence_text] if len(evidence_text) > 3000 else None,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Validate hook quality
        quality_warnings: list[str] = []
        hooks = result.get("hooks", [])
        awareness_levels_seen: set[str] = set()

        for hook in hooks:
            awareness_levels_seen.add(hook.get("awareness_level", "unknown"))
            if not hook.get("proof_anchor"):
                quality_warnings.append(
                    f"Hook missing proof anchor: '{hook.get('hook_text', '')[:50]}...'"
                )

        if len(awareness_levels_seen) < 3:
            quality_warnings.append(
                f"Only {len(awareness_levels_seen)} awareness levels covered — need at least 3"
            )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "hooks": result,
                "hook_count": len(hooks),
                "awareness_levels_covered": list(awareness_levels_seen),
                "evidence_count": len(memories),
            },
            quality_warnings=quality_warnings,
        )

"""Headline Generator Worker — generates headlines for finished ad copy.

Input:  Finished ad copy + headline primer
Output: 10 ranked headlines per piece of copy
Banks:  recall from OFFER, CREATIVE, PRIMERS
Guard:  Anti-generic enforced; complement body, don't repeat
"""

from __future__ import annotations

import json

from app.knowledge.base_training import get_training_context
from app.knowledge.primers import PrimerType, primer_store
from app.prompts.systems import HEADLINE_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.router import Capability, router
from app.services.llm.schemas import HEADLINE_GENERATION_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class HeadlineGeneratorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="headline_generator",
        purpose="Generate 10 ranked headlines for finished ad copy",
        accepted_input_types=["ad_copy", "headline_primer"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.PRIMERS],
        write_scope=[],
        steps=[
            "recall_creative_context",
            "load_headline_primer",
            "llm_generate_headlines",
            "rank_by_strength",
            "anti_generic_check",
        ],
        quality_checks=[
            "headlines_must_complement_not_repeat_hook",
            "anti_generic_test_on_all",
            "character_count_within_format_limits",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall headline-relevant context
        memories = await recall_for_worker(
            "headline_generator",
            account_id,
            "headline hook proof mechanism offer winning creative",
            offer_id=offer_id,
            top_k=20,
        )

        evidence_text = "\n".join(
            f"[{m.get('metadata', {}).get('evidence_type', 'unknown')}] {m.get('content', '')}"
            for m in memories
        )

        # Load headline primer
        primer_text = ""
        if offer_id:
            primer_content = await primer_store.get(account_id, offer_id, PrimerType.HEADLINE)
            if primer_content:
                primer_text = f"\n\n## Headline Primer\n{primer_content}"

        # Ad copy input
        ad_copy = params.get("ad_copy", "")
        if isinstance(ad_copy, dict):
            ad_copy = json.dumps(ad_copy, indent=1, default=str)

        training_context = get_training_context()
        system_prompt = f"{HEADLINE_GENERATOR_SYSTEM}\n\n{training_context}{primer_text}"

        result = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=system_prompt,
            user_prompt=(
                f"Generate 10 headlines for the following ad copy.\n\n"
                f"AD COPY:\n{ad_copy}\n\n"
                f"RECALLED CONTEXT ({len(memories)} items):\n{evidence_text}\n\n"
                f"Rank all headlines by expected performance. Cover multiple headline types "
                f"(proof-led, outcome-led, mechanism-led, identity-led, etc.)."
            ),
            temperature=0.6,
            max_tokens=4000,
            json_schema=HEADLINE_GENERATION_SCHEMA,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        quality_warnings: list[str] = []
        headlines = result.get("headlines", [])
        if len(headlines) < 5:
            quality_warnings.append(f"Only {len(headlines)} headlines generated — expected 10")

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "headlines": result,
                "headline_count": len(headlines),
                "evidence_count": len(memories),
            },
            quality_warnings=quality_warnings,
        )

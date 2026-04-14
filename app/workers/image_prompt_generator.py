"""Image Prompt Generator — converts image concepts into AI generation prompts.

Input:  Selected image concepts
Output: Ready-to-use prompts for Midjourney, GPT-Image, etc.
Banks:  recall from CREATIVE
Guard:  Native-feed aesthetic enforced; no stock-photo look
"""

from __future__ import annotations

import json

from app.knowledge.base_training import get_training_context
from app.prompts.systems import IMAGE_PROMPT_GENERATOR_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.llm.router import Capability, router
from app.services.llm.schemas import IMAGE_PROMPT_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class ImagePromptGeneratorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="image_prompt_generator",
        purpose="Convert selected image concepts into AI image generation prompts",
        accepted_input_types=["image_concepts"],
        recall_scope=[BankType.CREATIVE],
        write_scope=[],
        steps=[
            "parse_selected_concepts",
            "llm_generate_prompts",
            "enforce_native_aesthetic",
            "format_for_target_tool",
        ],
        quality_checks=[
            "prompts_must_specify_format",
            "native_feed_aesthetic_enforced",
            "no_stock_photo_look",
            "concept_traceability_required",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        params = worker_input.params

        concepts = params.get("image_concepts", [])
        if not concepts:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No image concepts provided"],
            )

        target_tool = params.get("target_tool", "midjourney")
        concepts_text = json.dumps(concepts, indent=1, default=str)

        training_context = get_training_context(include_examples=False)
        result = await router.generate(
            capability=Capability.CREATIVE_GENERATION,
            system_prompt=f"{IMAGE_PROMPT_GENERATOR_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Generate image prompts for these {len(concepts)} concepts.\n\n"
                f"TARGET TOOL: {target_tool}\n\n"
                f"CONCEPTS:\n{concepts_text}\n\n"
                f"For each concept, generate a detailed prompt optimized for {target_tool}. "
                f"ENFORCE: native-to-feed aesthetic, NOT polished/stock. "
                f"Include style notes, format (1:1, 4:5, 9:16), and negative constraints."
            ),
            temperature=0.5,
            max_tokens=6000,
            json_schema=IMAGE_PROMPT_SCHEMA,
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
                "image_prompts": result,
                "prompt_count": len(result.get("prompts", [])),
                "target_tool": target_tool,
            },
        )

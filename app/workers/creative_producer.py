"""Creative Producer Worker — multi-format creative output.

Produces complete creative packages across ALL formats, not just
static image + copy. Each format includes both the text AND the
visual/imagery direction as a unified concept.

Supported formats:
  - Static image ad (copy + image concept + prompt)
  - Video script (scene-by-scene with imagery direction, camera, audio)
  - Carousel (card sequence with individual image concepts)
  - UGC script (talking points + B-roll direction + text overlays)
  - Email (subject + preview + body with inline visual direction)
  - Landing page section (copy blocks + visual direction per section)
  - VSL script (full video sales letter with timestamps and visuals)

Input:  Brief + format type + primers + account skills
Output: Complete creative package ready for production
Banks:  recall from OFFER, CREATIVE, VOC, PRIMERS, SKILLS
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from app.knowledge.base_training import get_training_context
from app.knowledge.primers import PrimerType, primer_store
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.intelligence.skill_manager import SkillDomain, skill_manager
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

CREATIVE_PACKAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "format": {"type": "string"},
        "creative_package": {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "hook": {"type": "string"},
                "body": {"type": "string"},
                "cta": {"type": "string"},
                "awareness_level": {"type": "string"},
                "mechanism_bridge": {"type": "string"},
            },
        },
        "visual_direction": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "visual_concept": {"type": "string"},
                    "camera_direction": {"type": "string"},
                    "mood_lighting": {"type": "string"},
                    "text_overlay": {"type": "string"},
                    "audio_direction": {"type": "string"},
                    "duration_seconds": {"type": "number"},
                    "reference_style": {"type": "string"},
                    "production_notes": {"type": "string"},
                },
            },
        },
        "anti_generic_check": {"type": "string"},
        "production_feasibility": {"type": "string"},
    },
}

SYSTEM_PROMPT = """\
You are a Multi-Format Creative Producer. You create complete creative packages \
that include BOTH the text content AND the visual/imagery direction as a unified concept.

## Rules
- Every creative is text + visuals as ONE concept, not separate pieces
- Visual direction must be specific enough for a producer to execute without guessing
- Include camera angles, lighting, mood, text overlays, audio direction where relevant
- For video/UGC: scene-by-scene breakdown with timing
- For carousel: card-by-card with individual visual concepts
- For email: inline visual direction per section
- Native-to-platform aesthetic always — never looks like an ad
- The 13 reptile triggers apply to visuals across ALL formats
- Mechanism bridge must be present in every format
- Anti-generic test applies to EVERY element

## Format-Specific Guidance

### Static Image Ad
Copy (hook + body + CTA) + single image concept with detailed prompt direction.
Format: 1:1 or 4:5 only. Image must stop the scroll independently of copy.

### Video Script
Scene-by-scene with: visual (what's shown), audio (what's said/heard),
text overlay (on-screen text), camera direction, timing per scene.
Hook must capture in first 1-3 seconds. Total 15-60 seconds.

### Carousel
5-10 cards. Each card: headline + visual concept + supporting text.
First card is the hook — must stop scroll. Last card is CTA.
Story arc across cards — each earns the next swipe.

### UGC Script
Talking points (not a rigid script — UGC should feel natural), B-roll
direction (product shots, lifestyle moments), text overlay sequence,
opening hook (first 1-3 seconds), CTA direction.

### Email
Subject line + preview text + body sections. Each body section has
visual direction (hero image, inline images, CTA button styling).
The subject-preview-opening line must work as a unit.

### VSL Script
Full video sales letter: hook (0-30s), problem amplification (30-90s),
mechanism introduction (90-180s), proof sequence (180-300s), offer (300-360s),
CTA (360-420s). Each section has visual direction + audio.

### Landing Page Section
Headline + body copy + visual direction for each section of a page.
Includes above-fold, proof section, mechanism section, CTA section.\
"""


class CreativeProducerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="creative_producer",
        purpose="Produce complete multi-format creative packages with unified text + visual direction",
        accepted_input_types=["brief", "format_type"],
        recall_scope=[BankType.OFFER, BankType.CREATIVE, BankType.VOC, BankType.PRIMERS, BankType.SKILLS],
        write_scope=[BankType.CREATIVE],
        steps=[
            "recall_account_context_and_skills",
            "load_primers",
            "load_global_intelligence",
            "determine_format_requirements",
            "generate_creative_package",
            "validate_mechanism_and_anti_generic",
            "retain_to_creative_bank",
        ],
        quality_checks=[
            "visual_direction_must_be_specific_enough_to_produce",
            "mechanism_bridge_must_be_present",
            "anti_generic_test_all_elements",
            "format_specific_requirements_met",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        format_type = params.get("format", "static_image")
        brief = params.get("brief", {})
        brief_text = json.dumps(brief, indent=1, default=str) if isinstance(brief, dict) else str(brief)

        # Recall account context
        memories = await recall_for_worker(
            "creative_producer",
            account_id,
            "winning ad creative mechanism proof audience hook visual style format",
            offer_id=offer_id,
            top_k=25,
        )
        account_context = "\n".join(
            f"- {m.get('content', '')}" for m in memories
        )[:4000] if memories else ""

        # Load primers
        primer_text = ""
        if offer_id:
            primer_text = await primer_store.get_all_for_prompt(account_id, offer_id)

        # Load account skills
        skills_context = await skill_manager.get_skills_for_prompt(
            account_id,
            [SkillDomain.HOOKS, SkillDomain.VISUALS, SkillDomain.COPY, SkillDomain.FORMAT],
        )

        # Load global intelligence — best-effort. Empty when fewer than 3
        # accounts have generated reflections for this pattern category.
        global_context = ""
        try:
            from app.services.intelligence.global_brain import global_brain
            global_context = await global_brain.get_global_context_for_worker(
                "creative_producer",
                f"{format_type} creative winning pattern",
            )
        except Exception as exc:
            logger.debug(
                "creative_producer.global_context_unavailable format=%s error=%s",
                format_type, exc,
            )

        training_context = get_training_context(include_examples=False)
        full_system = (
            f"{SYSTEM_PROMPT}\n\n{training_context}"
            f"\n\n{primer_text}\n\n{skills_context}\n\n{global_context}"
        )

        result = await router.generate(
            capability=Capability.LONG_FORM_COPY,
            system_prompt=full_system,
            user_prompt=(
                f"Create a complete {format_type} creative package.\n\n"
                f"BRIEF:\n{brief_text}\n\n"
                f"ACCOUNT CONTEXT ({len(memories)} items):\n{account_context}\n\n"
                f"FORMAT: {format_type}\n\n"
                f"Include BOTH the text content AND detailed visual/imagery direction "
                f"for every section. The visual direction must be specific enough that "
                f"a producer can execute without guessing."
            ),
            temperature=0.6,
            max_tokens=8000,
            json_schema=CREATIVE_PACKAGE_SCHEMA,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse creative package"],
            )

        # Retain to CREATIVE bank
        package = result.get("creative_package", {})
        visual_count = len(result.get("visual_direction", []))
        summary = (
            f"Creative ({format_type}): "
            f"Hook: {package.get('hook', '')[:100]}. "
            f"Awareness: {package.get('awareness_level', '?')}. "
            f"Visual sections: {visual_count}. "
            f"Mechanism: {package.get('mechanism_bridge', '')}."
        )

        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=summary,
            offer_id=offer_id,
            source_type="generated",
            evidence_type="creative_package",
            confidence_score=0.7,
            extra_metadata={"format": format_type},
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "creative_package": result,
                "format": format_type,
                "visual_sections": visual_count,
            },
        )

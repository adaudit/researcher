"""Ad Analyzer Worker — deep multimodal creative analysis.

This is not a simple performance report. It UNDERSTANDS creatives:
- What's in the image (visual elements, composition, psychological triggers)
- What the copy does (hook structure, awareness level, proof density)
- What psychology is at play (reptile triggers, identity hooks, fear/desire)
- WHY the combination of image + copy + headline works or doesn't
- How the creative correlates to performance data

The ad analyzer feeds the self-learning loop:
  Performance data → Ad analysis → Skill updates → Better creative next cycle

Input:  Ad creative (image/video + copy + headline) + performance metrics
Output: Deep analysis + skill update recommendations + pattern tagging
Banks:  recall from CREATIVE, OFFER, SKILLS; write to CREATIVE, SKILLS
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.knowledge.base_training import get_training_context
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.intelligence.skill_manager import SkillDomain, skill_manager
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

AD_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visual_analysis": {
            "type": "object",
            "properties": {
                "primary_subject": {"type": "string"},
                "composition": {"type": "string"},
                "color_palette": {"type": "string"},
                "lighting_mood": {"type": "string"},
                "native_feed_score": {"type": "integer"},
                "scroll_stop_elements": {"type": "array", "items": {"type": "string"}},
                "reptile_triggers_present": {"type": "array", "items": {"type": "string"}},
                "text_overlays": {"type": "array", "items": {"type": "string"}},
                "production_style": {"type": "string"},
            },
        },
        "copy_analysis": {
            "type": "object",
            "properties": {
                "hook_text": {"type": "string"},
                "hook_type": {"type": "string"},
                "hook_strength": {"type": "integer"},
                "awareness_level": {"type": "string"},
                "mechanism_present": {"type": "boolean"},
                "mechanism_bridge": {"type": "string"},
                "proof_elements": {"type": "array", "items": {"type": "string"}},
                "proof_density_score": {"type": "integer"},
                "cta_text": {"type": "string"},
                "cta_friction_level": {"type": "string"},
                "word_count": {"type": "integer"},
                "anti_generic_score": {"type": "integer"},
            },
        },
        "psychology_analysis": {
            "type": "object",
            "properties": {
                "primary_emotion": {"type": "string"},
                "desire_targeted": {"type": "string"},
                "fear_leveraged": {"type": "string"},
                "identity_hook": {"type": "string"},
                "belief_shift_attempted": {"type": "string"},
                "psychological_triggers": {"type": "array", "items": {"type": "string"}},
                "persuasion_sequence": {"type": "string"},
            },
        },
        "synergy_analysis": {
            "type": "object",
            "properties": {
                "image_copy_alignment": {"type": "string"},
                "image_copy_score": {"type": "integer"},
                "headline_hook_relationship": {"type": "string"},
                "overall_coherence": {"type": "string"},
                "what_makes_it_work": {"type": "string"},
                "what_weakens_it": {"type": "string"},
            },
        },
        "performance_correlation": {
            "type": "object",
            "properties": {
                "performance_tier": {"type": "string"},
                "likely_success_factors": {"type": "array", "items": {"type": "string"}},
                "likely_failure_factors": {"type": "array", "items": {"type": "string"}},
                "improvement_directions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "tags": {
            "type": "object",
            "properties": {
                "hook_type": {"type": "string"},
                "format_type": {"type": "string"},
                "visual_style": {"type": "string"},
                "awareness_level": {"type": "string"},
                "segment": {"type": "string"},
                "angle": {"type": "string"},
            },
        },
    },
}


class AdAnalyzerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="ad_analyzer",
        purpose="Deep multimodal analysis of ad creatives — visual, copy, psychology, and performance correlation",
        accepted_input_types=["ad_creative", "performance_data"],
        recall_scope=[BankType.CREATIVE, BankType.OFFER, BankType.SKILLS],
        write_scope=[BankType.CREATIVE, BankType.SKILLS],
        steps=[
            "recall_account_context_and_skills",
            "analyze_visual_elements",
            "analyze_copy_structure",
            "analyze_psychology",
            "analyze_image_copy_synergy",
            "correlate_with_performance",
            "tag_creative_attributes",
            "update_account_skills",
            "retain_analysis",
        ],
        quality_checks=[
            "visual_analysis_must_identify_scroll_stop_elements",
            "copy_analysis_must_identify_hook_type_and_awareness",
            "psychology_must_map_emotional_triggers",
            "performance_correlation_must_be_evidence_based",
        ],
        escalation_rule="Escalate if creative uses regulated health/finance claims without proof",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall account context
        memories = await recall_for_worker(
            "ad_analyzer",
            account_id,
            "winning ad creative mechanism proof audience what works visual style hook",
            offer_id=offer_id,
            top_k=20,
        )

        account_context = "\n".join(
            f"- {m.get('content', '')}" for m in memories
        )[:3000] if memories else "No prior account context."

        # Load account skills
        skills_context = await skill_manager.get_skills_for_prompt(
            account_id,
            [SkillDomain.HOOKS, SkillDomain.VISUALS, SkillDomain.COPY, SkillDomain.AUDIENCE],
        )

        # Load global intelligence — best-effort, falls back to empty
        # context if the global brain hasn't aggregated yet (< 3 accounts).
        global_context = ""
        try:
            from app.services.intelligence.global_brain import global_brain
            global_context = await global_brain.get_global_context_for_worker(
                "ad_analyzer",
                "winning ad patterns visual psychology hook",
            )
        except Exception as exc:
            logger.debug("ad_analyzer.global_context_unavailable error=%s", exc)

        # Assemble the ad creative data
        ad_copy = params.get("ad_copy", "")
        headline = params.get("headline", "")
        image_data = params.get("image_data")  # bytes or None
        video_uri = params.get("video_uri")    # URI or None
        performance = params.get("performance_data", {})

        perf_text = json.dumps(performance, indent=1, default=str)[:2000] if performance else "No performance data."

        training_context = get_training_context(include_examples=False)
        system_prompt = (
            "You are an Ad Creative Analyst with deep expertise in visual psychology, "
            "direct response copywriting, and performance marketing.\n\n"
            "Your job is to UNDERSTAND creatives — not describe them. For every ad:\n"
            "1. VISUAL: What's in the image, what psychological triggers are at play, "
            "why would someone stop scrolling\n"
            "2. COPY: Hook structure, awareness level, mechanism bridge, proof density\n"
            "3. PSYCHOLOGY: What emotions, desires, fears, identity hooks are being leveraged\n"
            "4. SYNERGY: How do image + copy + headline work TOGETHER (or against each other)\n"
            "5. PERFORMANCE: Given the analysis, WHY is this ad performing the way it is\n\n"
            "The 13 reptile triggers: Ultra Real, Bizarre, Voyeur, Suffering/Pain, "
            "Gory/Visceral, Sexual, Primal Fear, Inside Joke, Old/Vintage, Victory Lap, "
            "Selfie/Demographic, Uncanny Object, Wildcard\n\n"
            f"{training_context}\n\n{skills_context}\n\n{global_context}"
        )

        user_prompt = (
            f"Analyze this ad creative in depth.\n\n"
            f"HEADLINE: {headline}\n\n"
            f"AD COPY:\n{ad_copy}\n\n"
            f"ACCOUNT CONTEXT:\n{account_context}\n\n"
            f"PERFORMANCE DATA:\n{perf_text}"
        )

        # Choose capability based on whether we have visual input
        if image_data:
            result = await router.generate(
                capability=Capability.IMAGE_ANALYSIS,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=8000,
                json_schema=AD_ANALYSIS_SCHEMA,
                images=[image_data],
            )
        elif video_uri:
            result = await router.generate(
                capability=Capability.VIDEO_ANALYSIS,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=8000,
                json_schema=AD_ANALYSIS_SCHEMA,
                video_uri=video_uri,
            )
        else:
            # Text-only analysis
            result = await router.generate(
                capability=Capability.STRATEGIC_REASONING,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=8000,
                json_schema=AD_ANALYSIS_SCHEMA,
            )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse ad analysis"],
            )

        # Retain the analysis
        tags = result.get("tags", {})
        perf_tier = result.get("performance_correlation", {}).get("performance_tier", "unknown")
        analysis_summary = (
            f"Ad analysis: Hook ({tags.get('hook_type', '?')}) + "
            f"Visual ({tags.get('visual_style', '?')}) + "
            f"Format ({tags.get('format_type', '?')}) = "
            f"Performance: {perf_tier}. "
            f"What works: {result.get('synergy_analysis', {}).get('what_makes_it_work', '?')}. "
            f"Awareness: {tags.get('awareness_level', '?')}."
        )

        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=analysis_summary,
            offer_id=offer_id,
            source_type="ad_analysis",
            evidence_type="creative_analysis",
            confidence_score=0.85,
            extra_metadata={
                "tags": tags,
                "performance_tier": perf_tier,
            },
        )

        # Auto-update skills if we have performance data
        skill_updates: list[dict[str, Any]] = []
        if performance and perf_tier != "unknown":
            for domain, attrs_key in [
                (SkillDomain.HOOKS, "copy_analysis"),
                (SkillDomain.VISUALS, "visual_analysis"),
                (SkillDomain.AUDIENCE, "psychology_analysis"),
            ]:
                domain_attrs = result.get(attrs_key, {})
                if domain_attrs:
                    update = await skill_manager.learn_from_performance(
                        account_id=account_id,
                        domain=domain,
                        performance_data=performance,
                        creative_attributes=domain_attrs,
                    )
                    if update.get("success"):
                        skill_updates.append(update)

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "ad_analysis": result,
                "skill_updates": skill_updates,
            },
        )

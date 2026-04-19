"""Image Analysis Pipeline Worker — static + carousel image processing.

Pipeline: Image(s) → Gemini analysis → structured JSON → categorization
          → creative library → embeddings

Handles both:
  - Static single images (one analysis per image)
  - Carousel ads (multi-card with narrative arc analysis)

Input:  Image bytes OR S3 key OR list of images (for carousel)
Output: Structured analysis + auto-categorization + embedding
Banks:  write to CREATIVE, SKILLS
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from app.knowledge.base_training import get_training_context
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router
from app.services.storage.object_store import object_store
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


STATIC_IMAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "format": {"type": "string"},
        "headline": {"type": "string"},
        "subheadline": {"type": "string"},
        "body_copy": {"type": "string"},
        "cta_text": {"type": "string"},
        "cta_type": {"type": "string"},
        "visual_elements": {
            "type": "object",
            "properties": {
                "dominant_colors": {"type": "array", "items": {"type": "string"}},
                "has_human": {"type": "boolean"},
                "human_type": {"type": "string"},
                "product_shown": {"type": "boolean"},
                "product_placement": {"type": "string"},
                "background_type": {"type": "string"},
                "text_style": {"type": "string"},
                "composition": {"type": "string"},
            },
        },
        "dr_tags": {
            "type": "object",
            "properties": {
                "hook_type": {"type": "string"},
                "urgency": {"type": "string"},
                "scarcity": {"type": "boolean"},
                "social_proof": {"type": "string"},
                "offer_type": {"type": "string"},
                "discount_value": {"type": "string"},
                "emotion_target": {"type": "string"},
            },
        },
        "reptile_triggers": {"type": "array", "items": {"type": "string"}},
        "target_audience": {"type": "string"},
        "ad_angle": {"type": "string"},
        "awareness_level": {"type": "string"},
        "ocr_all_text": {"type": "array", "items": {"type": "string"}},
        "scroll_stop_score": {"type": "integer"},
        "native_feed_score": {"type": "integer"},
        "why_it_works": {"type": "string"},
        "anti_generic_assessment": {"type": "string"},
    },
}


CAROUSEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "narrative_arc": {"type": "string"},
        "follows_pas_structure": {"type": "boolean"},
        "hook_card_index": {"type": "integer"},
        "cta_card_index": {"type": "integer"},
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "card_index": {"type": "integer"},
                    "role": {"type": "string"},  # hook | problem | solution | proof | offer | cta
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                    "visual_description": {"type": "string"},
                    "why_this_card": {"type": "string"},
                },
            },
        },
        "overall_effectiveness": {"type": "integer"},
        "awareness_level": {"type": "string"},
        "angle": {"type": "string"},
        "why_sequence_works": {"type": "string"},
    },
}


class ImageAnalysisPipelineWorker(BaseWorker):
    contract = SkillContract(
        skill_name="image_analysis_pipeline",
        purpose="Analyze static images and carousels with Gemini, auto-categorize, embed for similarity search",
        accepted_input_types=["image_bytes", "s3_key", "carousel_images"],
        recall_scope=[BankType.CREATIVE, BankType.OFFER],
        write_scope=[BankType.CREATIVE],
        steps=[
            "load_images",
            "gemini_analyze",
            "extract_categorization",
            "generate_embedding",
            "retain_to_memory",
        ],
        quality_checks=[
            "must_extract_ocr_text",
            "must_identify_dr_tags",
            "must_assess_scroll_stop",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        image_type = params.get("image_type", "static")  # static | carousel
        image_bytes = params.get("image_bytes")
        s3_key = params.get("storage_key")
        carousel_images = params.get("carousel_images", [])  # list of bytes or s3 keys

        # Load image(s)
        images_data: list[bytes] = []

        if image_type == "carousel" and carousel_images:
            for img in carousel_images:
                if isinstance(img, bytes):
                    images_data.append(img)
                elif isinstance(img, str):
                    # S3 key
                    data = await object_store.download("researcher-media", img)
                    if data:
                        images_data.append(data)
        else:
            if image_bytes:
                images_data.append(image_bytes)
            elif s3_key:
                data = await object_store.download("researcher-media", s3_key)
                if data:
                    images_data.append(data)

        if not images_data:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No image data — provide image_bytes, storage_key, or carousel_images"],
            )

        training_context = get_training_context(include_examples=False)

        # Route based on type
        if image_type == "carousel":
            analysis = await self._analyze_carousel(images_data, training_context)
        else:
            analysis = await self._analyze_static(images_data[0], training_context)

        if analysis.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Gemini analysis failed to parse"],
            )

        # Retain to memory
        asset_id = params.get("asset_id", f"img_{uuid4().hex[:12]}")

        if image_type == "carousel":
            summary = (
                f"Carousel analysis: {len(analysis.get('cards', []))} cards. "
                f"Narrative: {analysis.get('narrative_arc', 'unknown')}. "
                f"PAS structure: {analysis.get('follows_pas_structure', False)}. "
                f"Awareness: {analysis.get('awareness_level', '?')}. "
                f"Effectiveness: {analysis.get('overall_effectiveness', '?')}/10. "
                f"Why it works: {analysis.get('why_sequence_works', '')[:200]}"
            )
        else:
            summary = (
                f"Image analysis ({analysis.get('format', 'unknown')}): "
                f"Headline: {analysis.get('headline', '')[:100]}. "
                f"Hook type: {analysis.get('dr_tags', {}).get('hook_type', '?')}. "
                f"Scroll stop: {analysis.get('scroll_stop_score', '?')}/10. "
                f"Awareness: {analysis.get('awareness_level', '?')}. "
                f"Why: {analysis.get('why_it_works', '')[:200]}"
            )

        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=summary,
            offer_id=offer_id,
            source_type="image_analysis",
            evidence_type="creative_analysis",
            confidence_score=0.85,
            extra_metadata={
                "asset_id": asset_id,
                "image_type": image_type,
                "card_count": len(images_data) if image_type == "carousel" else 1,
            },
        )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "asset_id": asset_id,
                "image_type": image_type,
                "analysis": analysis,
            },
        )

    async def _analyze_static(
        self,
        image_bytes: bytes,
        training_context: str,
    ) -> dict[str, Any]:
        """Analyze a single static image."""
        return await router.generate(
            capability=Capability.IMAGE_ANALYSIS,
            system_prompt=(
                "You are a Direct Response Static Ad Analyst. Analyze this image "
                "and extract ALL structured data.\n\n"
                "Extract:\n"
                "- All visible text (OCR everything — headline, body, CTA, labels)\n"
                "- Visual elements (colors, composition, humans, product, background)\n"
                "- DR tags (hook type, urgency, scarcity, social proof, offer type, emotion)\n"
                "- Reptile triggers present (Ultra Real, Bizarre, Voyeur, Suffering, "
                "Gory, Sexual, Primal Fear, Inside Joke, Old/Vintage, Victory Lap, "
                "Selfie/Demographic, Uncanny Object, Wildcard)\n"
                "- Target audience and ad angle\n"
                "- Awareness level\n"
                "- Scroll-stop score (1-10) and native-feed score (1-10)\n"
                "- Why it works / why it might not\n"
                "- Anti-generic assessment\n\n"
                f"{training_context}"
            ),
            user_prompt="Analyze this ad image fully. Extract every piece of structured data.",
            temperature=0.2,
            max_tokens=5000,
            json_schema=STATIC_IMAGE_SCHEMA,
            images=[image_bytes],
        )

    async def _analyze_carousel(
        self,
        images: list[bytes],
        training_context: str,
    ) -> dict[str, Any]:
        """Analyze a carousel ad with narrative arc assessment."""
        return await router.generate(
            capability=Capability.IMAGE_ANALYSIS,
            system_prompt=(
                "You are a Direct Response Carousel Ad Analyst. Analyze this "
                f"{len(images)}-card carousel ad.\n\n"
                "For EACH card, extract:\n"
                "- Role in the sequence (hook | problem | solution | proof | offer | cta)\n"
                "- Headline, body copy, visual description\n"
                "- Why this card earns the swipe to the next\n\n"
                "Then analyze the OVERALL narrative arc:\n"
                "- Does the sequence follow Hook → Problem → Solution → Proof → CTA?\n"
                "- Which card is the hook? Which is the CTA?\n"
                "- What makes the sequence work (or not)?\n"
                "- Overall effectiveness (1-10)\n\n"
                f"{training_context}"
            ),
            user_prompt=(
                f"Analyze this {len(images)}-card carousel ad. "
                f"Provide both per-card analysis and overall narrative arc assessment."
            ),
            temperature=0.2,
            max_tokens=8000,
            json_schema=CAROUSEL_SCHEMA,
            images=images,
        )

"""Creative library — search, categorize, and study creative assets.

The creative library is the system's searchable intelligence database.
Every creative asset (own ads, competitor swipes, reference images,
video clips) can be:

1. Searched by any combination of dimensions (format, style, hook type,
   awareness level, segment, performance tier, DR tags)
2. Analyzed and auto-categorized when ingested
3. Studied — the system can pull relevant swipes when creating new work
4. Compared — find similar creatives, identify what's different about winners
5. Learned from — performance data enriches the categorization over time
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.creative import CreativeAnalysis, CreativeAsset, SwipeEntry
from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)

# All the dimensions you can categorize/filter creatives by
CATEGORIZATION_DIMENSIONS = {
    "format_type": [
        "headline_plus_image", "before_after", "infographic", "testimonial_card",
        "meme_style", "screenshot_chat", "ugc_selfie", "note_from_founder",
        "scientific_study", "comparison_chart", "talking_head_ugc",
        "problem_solution_video", "listicle_video", "in_feed_vsl",
        "green_screen_explainer", "story_carousel", "educational_carousel",
        "story_email", "proof_stack_email", "custom",
    ],
    "visual_style": [
        "ugc_native", "polished_studio", "lo_fi", "meme", "screenshot",
        "medical_scientific", "lifestyle", "product_hero", "text_heavy",
        "vintage_retro", "dark_moody", "bright_clean", "raw_authentic",
        "documentary", "animated", "collage", "custom",
    ],
    "hook_type": [
        "pain_point", "curiosity", "contrarian", "story", "proof_led",
        "identity", "consequence", "pattern_interrupt", "question",
        "bold_claim", "social_proof_led", "urgency", "custom",
    ],
    "awareness_level": [
        "unaware", "problem_aware", "solution_aware", "product_aware", "most_aware",
    ],
    "dr_tags": [
        "pain_point", "curiosity", "pattern_interrupt", "social_proof",
        "urgency", "scarcity", "free_trial", "guarantee", "authority",
        "transformation", "fear", "FOMO", "mechanism_reveal", "proof_stack",
    ],
    "segment_type": [  # for video clips
        "HOOK", "PROBLEM_AGITATE", "SOLUTION", "DEMO", "SOCIAL_PROOF",
        "OBJECTION_HANDLE", "CTA", "TRANSITION", "B_ROLL",
    ],
    "performance_tier": [
        "winner", "strong", "average", "weak", "loser", "untested",
    ],
    "ownership": [
        "own", "competitor", "swipe", "reference", "template",
    ],
}

AUTO_CATEGORIZE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "format_type": {"type": "string"},
        "visual_style": {"type": "string"},
        "hook_type": {"type": "string"},
        "awareness_level": {"type": "string"},
        "angle": {"type": "string"},
        "segment_target": {"type": "string"},
        "emotional_tone": {"type": "string"},
        "dr_tags": {"type": "array", "items": {"type": "string"}},
        "reptile_triggers": {"type": "array", "items": {"type": "string"}},
        "why_it_works": {"type": "string"},
        "what_to_study": {"type": "string"},
    },
}


class CreativeLibrary:
    """Search, categorize, and study creative assets."""

    async def auto_categorize(
        self,
        headline: str = "",
        body_copy: str = "",
        visual_description: str = "",
        image_data: bytes | None = None,
    ) -> dict[str, Any]:
        """Auto-categorize a creative across all dimensions using LLM.

        This is called when a new creative is ingested — the system
        automatically tags it across every dimension so it's immediately
        searchable and usable for learning.
        """
        content_parts = []
        if headline:
            content_parts.append(f"HEADLINE: {headline}")
        if body_copy:
            content_parts.append(f"BODY COPY: {body_copy}")
        if visual_description:
            content_parts.append(f"VISUAL: {visual_description}")

        content_text = "\n".join(content_parts) if content_parts else "No text content."

        capability = Capability.IMAGE_ANALYSIS if image_data else Capability.TEXT_EXTRACTION

        result = await router.generate(
            capability=capability,
            system_prompt=(
                "You are a Creative Categorization Engine. Categorize this ad creative "
                "across every dimension.\n\n"
                f"FORMAT TYPES: {', '.join(CATEGORIZATION_DIMENSIONS['format_type'])}\n"
                f"VISUAL STYLES: {', '.join(CATEGORIZATION_DIMENSIONS['visual_style'])}\n"
                f"HOOK TYPES: {', '.join(CATEGORIZATION_DIMENSIONS['hook_type'])}\n"
                f"AWARENESS LEVELS: {', '.join(CATEGORIZATION_DIMENSIONS['awareness_level'])}\n"
                f"DR TAGS: {', '.join(CATEGORIZATION_DIMENSIONS['dr_tags'])}\n\n"
                "Also identify the 13 reptile triggers if present: Ultra Real, Bizarre, "
                "Voyeur, Suffering/Pain, Gory/Visceral, Sexual, Primal Fear, Inside Joke, "
                "Old/Vintage, Victory Lap, Selfie/Demographic, Uncanny Object, Wildcard.\n\n"
                "Explain WHY it works and WHAT is worth studying about this creative."
            ),
            user_prompt=f"Categorize this creative:\n\n{content_text}",
            temperature=0.2,
            max_tokens=3000,
            json_schema=AUTO_CATEGORIZE_SCHEMA,
            images=[image_data] if image_data else None,
        )

        return result

    async def find_similar(
        self,
        db: AsyncSession,
        account_id: str,
        *,
        reference_asset_id: str | None = None,
        query_text: str | None = None,
        embedding_type: str = "content",
        ownership: str | None = None,
        performance_tier: str | None = None,
        limit: int = 10,
    ) -> list[tuple[CreativeAsset, float]]:
        """Find creative assets similar to a reference.

        Two modes:
        1. Reference asset: pass reference_asset_id, find similar to that asset
        2. Query text: pass query_text, find ads matching that description

        embedding_type: "content" (text-based) or "visual" (image-based)

        Returns list of (asset, distance) tuples sorted by similarity
        (lower distance = more similar).
        """
        from app.services.intelligence.embeddings import embedding_service

        # Get the query vector
        query_vec = None
        if reference_asset_id:
            ref_stmt = select(CreativeAsset).where(
                CreativeAsset.id == reference_asset_id,
                CreativeAsset.account_id == account_id,
            )
            ref_result = await db.execute(ref_stmt)
            ref_asset = ref_result.scalar_one_or_none()
            if ref_asset:
                query_vec = (
                    ref_asset.content_embedding if embedding_type == "content"
                    else ref_asset.visual_embedding
                )
        elif query_text:
            query_vec = await embedding_service.embed_text(query_text)

        if query_vec is None:
            logger.warning("similarity.no_query_vector")
            return []

        # Build the query
        embedding_col = (
            CreativeAsset.content_embedding if embedding_type == "content"
            else CreativeAsset.visual_embedding
        )

        conditions = [
            CreativeAsset.account_id == account_id,
            embedding_col.is_not(None),
        ]
        if reference_asset_id:
            conditions.append(CreativeAsset.id != reference_asset_id)
        if ownership:
            conditions.append(CreativeAsset.ownership == ownership)
        if performance_tier:
            conditions.append(CreativeAsset.performance_tier == performance_tier)

        distance = embedding_col.cosine_distance(query_vec)
        stmt = (
            select(CreativeAsset, distance.label("distance"))
            .where(and_(*conditions))
            .order_by(distance)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def find_similar_winners(
        self,
        db: AsyncSession,
        account_id: str,
        query_text: str,
        *,
        limit: int = 10,
    ) -> list[tuple[CreativeAsset, float]]:
        """Find historical winners similar to a task description.

        Useful when creating new work — "find winners similar to what I'm
        trying to make" for reference and pattern extraction.
        """
        return await self.find_similar(
            db, account_id,
            query_text=query_text,
            performance_tier="winner",
            limit=limit,
        )

    async def search(
        self,
        db: AsyncSession,
        account_id: str,
        *,
        format_type: str | None = None,
        visual_style: str | None = None,
        hook_type: str | None = None,
        awareness_level: str | None = None,
        performance_tier: str | None = None,
        ownership: str | None = None,
        asset_type: str | None = None,
        limit: int = 50,
    ) -> list[CreativeAsset]:
        """Search creative assets by any combination of dimensions."""
        conditions = [CreativeAsset.account_id == account_id]

        if format_type:
            conditions.append(CreativeAsset.format_type == format_type)
        if visual_style:
            conditions.append(CreativeAsset.visual_style == visual_style)
        if hook_type:
            conditions.append(CreativeAsset.hook_type == hook_type)
        if awareness_level:
            conditions.append(CreativeAsset.awareness_level == awareness_level)
        if performance_tier:
            conditions.append(CreativeAsset.performance_tier == performance_tier)
        if ownership:
            conditions.append(CreativeAsset.ownership == ownership)
        if asset_type:
            conditions.append(CreativeAsset.asset_type == asset_type)

        stmt = (
            select(CreativeAsset)
            .where(and_(*conditions))
            .order_by(CreativeAsset.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def search_swipes(
        self,
        db: AsyncSession,
        account_id: str,
        *,
        swipe_source: str | None = None,
        format_type: str | None = None,
        hook_type: str | None = None,
        awareness_level: str | None = None,
        industry: str | None = None,
        curation_status: str = "active",
        limit: int = 50,
    ) -> list[SwipeEntry]:
        """Search the swipe file by category."""
        conditions = [
            SwipeEntry.account_id == account_id,
            SwipeEntry.curation_status == curation_status,
        ]

        if swipe_source:
            conditions.append(SwipeEntry.swipe_source == swipe_source)
        if format_type:
            conditions.append(SwipeEntry.format_type == format_type)
        if hook_type:
            conditions.append(SwipeEntry.hook_type == hook_type)
        if awareness_level:
            conditions.append(SwipeEntry.awareness_level == awareness_level)
        if industry:
            conditions.append(SwipeEntry.industry == industry)

        stmt = (
            select(SwipeEntry)
            .where(and_(*conditions))
            .order_by(SwipeEntry.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_swipes_for_prompt(
        self,
        db: AsyncSession,
        account_id: str,
        *,
        format_type: str | None = None,
        hook_type: str | None = None,
        awareness_level: str | None = None,
        limit: int = 8,
    ) -> str:
        """Get relevant swipes formatted for worker prompt injection.

        When the system is creating new work, it can pull relevant
        swipes as reference/inspiration — grounded in real winning
        creatives, not generic knowledge.
        """
        swipes = await self.search_swipes(
            db, account_id,
            format_type=format_type,
            hook_type=hook_type,
            awareness_level=awareness_level,
            limit=limit,
        )

        if not swipes:
            return ""

        lines = ["## Reference Swipes (studied creatives from your library)\n"]
        for s in swipes:
            lines.append(
                f"- **{s.format_type or 'unknown'} / {s.hook_type or 'unknown'}** "
                f"({s.swipe_source}): {s.what_to_steal or s.study_notes or 'No notes'}"
            )

        return "\n".join(lines)

    async def ingest_and_categorize(
        self,
        db: AsyncSession,
        account_id: str,
        *,
        asset_type: str,
        ownership: str = "own",
        headline: str = "",
        body_copy: str = "",
        source_url: str = "",
        source_platform: str = "",
        advertiser_name: str = "",
        image_data: bytes | None = None,
        offer_id: str | None = None,
        performance_data: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> CreativeAsset:
        """Ingest a creative, auto-categorize it, and store it.

        This is the main entry point for adding creatives to the library.
        The system automatically categorizes across all dimensions.
        """
        asset_id = f"ca_{uuid4().hex[:12]}"

        # Auto-categorize
        categories = await self.auto_categorize(
            headline=headline,
            body_copy=body_copy,
            image_data=image_data,
        )

        # Determine performance tier if we have data
        perf_tier = "untested"
        if performance_data:
            roas = performance_data.get("roas", 0)
            if roas > 3.0:
                perf_tier = "winner"
            elif roas > 2.0:
                perf_tier = "strong"
            elif roas > 1.0:
                perf_tier = "average"
            elif roas > 0:
                perf_tier = "weak"
            else:
                perf_tier = "untested"

        # Auto-generate embeddings
        from app.services.intelligence.embeddings import embedding_service
        content_embedding = await embedding_service.embed_creative_content(
            headline=headline,
            body_copy=body_copy,
            categories=categories,
        )
        visual_embedding = None
        if image_data:
            visual_embedding = await embedding_service.embed_visual(image_bytes=image_data)

        asset = CreativeAsset(
            id=asset_id,
            account_id=account_id,
            offer_id=offer_id,
            asset_type=asset_type,
            ownership=ownership,
            source_platform=source_platform,
            source_url=source_url,
            advertiser_name=advertiser_name,
            headline=headline,
            body_copy=body_copy,
            format_type=categories.get("format_type"),
            visual_style=categories.get("visual_style"),
            hook_type=categories.get("hook_type"),
            angle=categories.get("angle"),
            awareness_level=categories.get("awareness_level"),
            segment_target=categories.get("segment_target"),
            emotional_tone=categories.get("emotional_tone"),
            dr_tags=categories.get("dr_tags"),
            performance_tier=perf_tier,
            processing_status="analyzed",
            content_embedding=content_embedding,
            visual_embedding=visual_embedding,
            extra_metadata={
                **(extra_metadata or {}),
                "auto_categories": categories,
                "why_it_works": categories.get("why_it_works"),
                "what_to_study": categories.get("what_to_study"),
            },
        )

        if performance_data:
            asset.spend = performance_data.get("spend")
            asset.impressions = performance_data.get("impressions")
            asset.clicks = performance_data.get("clicks")
            asset.ctr = performance_data.get("ctr")
            asset.cpa = performance_data.get("cpa")
            asset.roas = performance_data.get("roas")
            asset.hook_rate = performance_data.get("hook_rate")
            asset.thumb_stop_ratio = performance_data.get("thumb_stop_ratio")

        db.add(asset)
        await db.commit()
        await db.refresh(asset)

        # Auto-create swipe entry if it's a competitor or reference
        if ownership in ("competitor", "swipe", "reference"):
            swipe = SwipeEntry(
                id=f"sw_{uuid4().hex[:12]}",
                account_id=account_id,
                asset_id=asset_id,
                offer_id=offer_id,
                swipe_source="competitor" if ownership == "competitor" else ownership,
                study_notes=categories.get("what_to_study"),
                why_it_works=categories.get("why_it_works"),
                what_to_steal=categories.get("what_to_study"),
                format_type=categories.get("format_type"),
                visual_style=categories.get("visual_style"),
                hook_type=categories.get("hook_type"),
                angle=categories.get("angle"),
                awareness_level=categories.get("awareness_level"),
                curated_by="system",
            )
            db.add(swipe)
            await db.commit()

        logger.info(
            "creative_library.ingested asset=%s type=%s ownership=%s format=%s",
            asset_id, asset_type, ownership, categories.get("format_type"),
        )

        return asset


# Module-level singleton
creative_library = CreativeLibrary()

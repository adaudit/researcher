"""Meta (Facebook/Instagram) ad creative and comment extractor.

Knows Meta's data structure: ad library format, comment threading,
reaction types, page post structure, and Instagram-specific fields.
Uses Gemini for image/video ad analysis and fast models for text.
"""

from __future__ import annotations

from typing import Any

from app.services.llm.router import Capability, router
from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class MetaAdsExtractor(BaseExtractor):
    platform = SourcePlatform.META_ADS

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        ads = raw_data.get("ads", [])
        comments = raw_data.get("comments", [])

        # ── Extract from ad creatives ──
        for ad in ads:
            # Primary text / body
            body = ad.get("body", {}).get("text", "") or ad.get("ad_creative_body", "")
            if body and len(body) > 10:
                payloads.append(ExtractionPayload(
                    content=body,
                    source_platform=self.platform,
                    extraction_type="ad_copy",
                    source_url=ad.get("ad_snapshot_url"),
                    source_id=ad.get("id"),
                    engagement={
                        "impressions": ad.get("impressions", {}).get("lower_bound"),
                        "spend": ad.get("spend", {}).get("lower_bound"),
                    },
                    platform_metadata={
                        "page_name": ad.get("page_name"),
                        "ad_delivery_start": ad.get("ad_delivery_start_time"),
                        "ad_delivery_stop": ad.get("ad_delivery_stop_time"),
                        "platforms": ad.get("publisher_platforms", []),
                        "demographic_distribution": ad.get("demographic_distribution"),
                    },
                    suggested_category="hook" if len(body.split()) < 30 else "ad_copy",
                ))

            # Title / headline
            title = ad.get("ad_creative_link_title", "")
            if title:
                payloads.append(ExtractionPayload(
                    content=title,
                    source_platform=self.platform,
                    extraction_type="headline",
                    source_id=ad.get("id"),
                    suggested_category="hook",
                ))

            # Link description
            desc = ad.get("ad_creative_link_description", "")
            if desc and len(desc) > 10:
                payloads.append(ExtractionPayload(
                    content=desc,
                    source_platform=self.platform,
                    extraction_type="ad_copy",
                    source_id=ad.get("id"),
                ))

            # Image analysis via Gemini
            image_data = ad.get("image_bytes")
            if image_data:
                try:
                    visual = await router.generate(
                        capability=Capability.IMAGE_ANALYSIS,
                        system_prompt=(
                            "Extract text, claims, and visual elements from this ad creative. "
                            "Note: hook text overlays, proof elements (badges, stats), "
                            "emotional imagery, and CTA buttons."
                        ),
                        user_prompt="Extract all text and strategic elements from this ad image.",
                        images=[image_data],
                        temperature=0.1,
                        max_tokens=1500,
                        json_schema={
                            "type": "object",
                            "properties": {
                                "text_overlays": {"type": "array", "items": {"type": "string"}},
                                "visual_elements": {"type": "array", "items": {"type": "string"}},
                                "cta_text": {"type": "string"},
                                "emotional_tone": {"type": "string"},
                            },
                        },
                    )
                    for text in visual.get("text_overlays", []):
                        payloads.append(ExtractionPayload(
                            content=text,
                            source_platform=self.platform,
                            extraction_type="text_overlay",
                            source_id=ad.get("id"),
                            suggested_category="hook",
                            platform_metadata={"visual_context": visual},
                        ))
                except Exception:
                    pass

        # ── Extract from comments ──
        for comment in comments:
            text = comment.get("message", "") or comment.get("text", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_url=comment.get("permalink_url"),
                source_id=comment.get("id"),
                author=comment.get("from", {}).get("name"),
                timestamp=comment.get("created_time"),
                engagement={
                    "likes": comment.get("like_count", 0),
                    "replies": comment.get("comment_count", 0),
                },
                platform_metadata={
                    "parent_id": comment.get("parent", {}).get("id"),
                    "is_reply": bool(comment.get("parent")),
                    "attachment_type": comment.get("attachment", {}).get("type"),
                },
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(ads) + len(comments),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

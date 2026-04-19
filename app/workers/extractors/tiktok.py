"""TikTok ad and comment extractor.

Knows TikTok's data structure: Creative Center format, TopView/Spark ads,
comment threading, video descriptions, hashtag challenges, and
TikTok-specific engagement metrics (shares are unusually important).
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


class TikTokExtractor(BaseExtractor):
    platform = SourcePlatform.TIKTOK

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        videos = raw_data.get("videos", [])
        comments = raw_data.get("comments", [])
        ads = raw_data.get("ads", [])

        # ── Extract from video content ──
        for video in videos:
            desc = video.get("desc", "") or video.get("description", "")
            if desc:
                payloads.append(ExtractionPayload(
                    content=desc,
                    source_platform=self.platform,
                    extraction_type="video_description",
                    source_url=video.get("share_url") or f"https://tiktok.com/@{video.get('author', {}).get('uniqueId')}/video/{video.get('id')}",
                    source_id=video.get("id"),
                    author=video.get("author", {}).get("uniqueId"),
                    timestamp=video.get("createTime"),
                    engagement={
                        "views": video.get("stats", {}).get("playCount", 0),
                        "likes": video.get("stats", {}).get("diggCount", 0),
                        "comments": video.get("stats", {}).get("commentCount", 0),
                        "shares": video.get("stats", {}).get("shareCount", 0),
                        "saves": video.get("stats", {}).get("collectCount", 0),
                    },
                    platform_metadata={
                        "hashtags": [h.get("name") for h in video.get("challenges", [])],
                        "sounds": video.get("music", {}).get("title"),
                        "duration": video.get("video", {}).get("duration"),
                        "is_ad": video.get("isAd", False),
                        # TikTok-specific: share rate is a strong quality signal
                        "share_rate": (
                            video.get("stats", {}).get("shareCount", 0) /
                            max(video.get("stats", {}).get("playCount", 1), 1)
                        ),
                    },
                    suggested_category="hook" if len(desc.split()) < 20 else "ad_copy",
                ))

            # Video analysis via Gemini (if video URI available)
            video_uri = video.get("video_uri")
            if video_uri:
                try:
                    visual = await router.generate(
                        capability=Capability.VIDEO_ANALYSIS,
                        system_prompt=(
                            "Analyze this TikTok video for marketing elements. "
                            "TikTok hooks must grab in the first 1-3 seconds. "
                            "Note: opening hook technique, text overlays, "
                            "transitions, proof elements, CTA placement, "
                            "and what makes this native to TikTok vs generic."
                        ),
                        user_prompt="Extract the opening hook, key claims, and proof elements from this TikTok.",
                        video_uri=video_uri,
                        temperature=0.2,
                        max_tokens=2000,
                        json_schema={
                            "type": "object",
                            "properties": {
                                "opening_hook": {"type": "string"},
                                "hook_technique": {"type": "string"},
                                "text_overlays": {"type": "array", "items": {"type": "string"}},
                                "proof_elements": {"type": "array", "items": {"type": "string"}},
                                "format_type": {"type": "string"},
                                "tiktok_native_elements": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    )
                    if visual.get("opening_hook"):
                        payloads.append(ExtractionPayload(
                            content=visual["opening_hook"],
                            source_platform=self.platform,
                            extraction_type="video_hook",
                            source_id=video.get("id"),
                            suggested_category="hook",
                            platform_metadata={"video_analysis": visual},
                        ))
                except Exception:
                    pass

        # ── Extract from comments ──
        for comment in comments:
            text = comment.get("text", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_id=comment.get("cid"),
                author=comment.get("user", {}).get("unique_id"),
                timestamp=comment.get("create_time"),
                engagement={
                    "likes": comment.get("digg_count", 0),
                    "replies": comment.get("reply_comment_total", 0),
                },
                platform_metadata={
                    "is_reply": bool(comment.get("reply_id")),
                    "is_author_reply": comment.get("is_author_digged", False),
                },
            ))

        # ── Extract from Creative Center ads ──
        for ad in ads:
            headline = ad.get("title", "") or ad.get("ad_title", "")
            if headline:
                payloads.append(ExtractionPayload(
                    content=headline,
                    source_platform=self.platform,
                    extraction_type="headline",
                    source_id=ad.get("material_id"),
                    engagement={
                        "ctr": ad.get("ctr"),
                        "cvr": ad.get("cvr"),
                        "impressions": ad.get("show_cnt"),
                    },
                    platform_metadata={
                        "industry": ad.get("industry_name"),
                        "objective": ad.get("objective_name"),
                        "country": ad.get("country_code"),
                        "ad_format": ad.get("ad_format"),
                    },
                    suggested_category="hook",
                ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(videos) + len(comments) + len(ads),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

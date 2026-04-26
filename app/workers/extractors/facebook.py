"""Facebook extractor — post text, comments, ad library data.

Facebook-specific: reactions breakdown (love/angry/sad reveal emotional
response), comment threads reveal objections and desires, ad library
data reveals competitor spend signals and running duration.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class FacebookExtractor(BaseExtractor):
    platform = SourcePlatform.FACEBOOK

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        posts = raw_data.get("posts", [])
        comments = raw_data.get("comments", [])
        ads = raw_data.get("ads", [])
        if isinstance(raw_data, list):
            posts = raw_data

        # ── Extract from posts ──
        for post in posts:
            text = post.get("message", "") or post.get("text", "") or post.get("content", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            reactions = post.get("reactions", {})
            total_reactions = sum(reactions.values()) if isinstance(reactions, dict) else (reactions or 0)

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="post",
                exact_quote=True,
                source_url=post.get("permalink_url") or post.get("url"),
                source_id=post.get("id"),
                author=post.get("from", {}).get("name") or post.get("author"),
                timestamp=post.get("created_time") or post.get("created_at"),
                engagement={
                    "reactions": total_reactions,
                    "comments": post.get("comments", {}).get("summary", {}).get("total_count", 0) if isinstance(post.get("comments"), dict) else 0,
                    "shares": post.get("shares", {}).get("count", 0) if isinstance(post.get("shares"), dict) else 0,
                },
                platform_metadata={
                    "reactions_breakdown": reactions if isinstance(reactions, dict) else {},
                    "post_type": post.get("type", "status"),
                    "is_ad": bool(post.get("is_ad") or post.get("ad_id")),
                },
            ))

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
                source_id=comment.get("id"),
                author=comment.get("from", {}).get("name") or comment.get("author"),
                timestamp=comment.get("created_time") or comment.get("created_at"),
                engagement={
                    "likes": comment.get("like_count", 0),
                },
                platform_metadata={
                    "is_reply": bool(comment.get("parent", {}).get("id")),
                },
            ))

        # ── Extract from ad library data ──
        for ad in ads:
            ad_text = ad.get("ad_creative_bodies", [""])[0] if isinstance(ad.get("ad_creative_bodies"), list) else ad.get("body", "")
            if not ad_text:
                skipped += 1
                continue

            payloads.append(ExtractionPayload(
                content=ad_text,
                source_platform=self.platform,
                extraction_type="ad_copy",
                source_id=ad.get("id") or ad.get("ad_id"),
                author=ad.get("page_name") or ad.get("advertiser"),
                timestamp=ad.get("ad_delivery_start_time") or ad.get("start_date"),
                engagement={},
                platform_metadata={
                    "ad_library": True,
                    "start_date": ad.get("ad_delivery_start_time"),
                    "is_active": ad.get("ad_delivery_stop_time") is None,
                    "platforms": ad.get("publisher_platforms", []),
                    "spend_range": ad.get("spend", {}),
                },
                suggested_category="hook",
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(posts) + len(comments) + len(ads),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

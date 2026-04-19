"""Instagram extractor — post captions, comments, engagement, hashtags.

Instagram-specific signals: saves indicate high-value content,
carousel completion rate signals engaging content, caption length
patterns reveal what works for the audience.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class InstagramExtractor(BaseExtractor):
    platform = SourcePlatform.INSTAGRAM

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
        if isinstance(raw_data, list):
            posts = raw_data

        # ── Extract from posts ──
        for post in posts:
            caption = post.get("caption", "") or post.get("text", "")
            if not caption or len(caption.split()) < 3:
                skipped += 1
                continue

            likes = post.get("likes", 0) or post.get("like_count", 0)
            comments_count = post.get("comments", 0) or post.get("comment_count", 0)
            saves = post.get("saves", 0) or post.get("save_count", 0)
            shares = post.get("shares", 0) or post.get("share_count", 0)
            post_type = post.get("type", "image") or post.get("media_type", "image")

            hashtags = post.get("hashtags", [])
            if not hashtags and "#" in caption:
                import re
                hashtags = re.findall(r"#(\w+)", caption)

            payloads.append(ExtractionPayload(
                content=caption,
                source_platform=self.platform,
                extraction_type="post_caption",
                exact_quote=True,
                source_url=post.get("url") or post.get("permalink"),
                source_id=post.get("id") or post.get("post_id"),
                author=post.get("username") or post.get("author"),
                timestamp=post.get("timestamp") or post.get("created_at"),
                engagement={
                    "likes": likes,
                    "comments": comments_count,
                    "saves": saves,
                    "shares": shares,
                },
                platform_metadata={
                    "post_type": post_type,
                    "hashtags": hashtags,
                    "is_carousel": post_type in ("carousel", "album", "sidecar"),
                    "is_reel": post_type in ("reel", "video", "clips"),
                    "carousel_count": post.get("carousel_media_count", 0),
                },
                suggested_category="hook" if saves > likes * 0.05 else None,
            ))

        # ── Extract from comments ──
        for comment in comments:
            text = comment.get("text", "") or comment.get("content", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_id=comment.get("id"),
                author=comment.get("username") or comment.get("author"),
                timestamp=comment.get("timestamp") or comment.get("created_at"),
                engagement={
                    "likes": comment.get("likes", 0) or comment.get("like_count", 0),
                },
                platform_metadata={
                    "is_reply": bool(comment.get("parent_id") or comment.get("replied_to")),
                },
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(posts) + len(comments),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

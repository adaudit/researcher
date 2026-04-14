"""LinkedIn extractor — post text, comments, professional context.

LinkedIn-specific: professional context matters more than other platforms.
Comment quality is typically higher (less spam, more substantive).
Engagement rates are lower but more meaningful — a comment from a
decision-maker outweighs 100 likes.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class LinkedInExtractor(BaseExtractor):
    platform = SourcePlatform.LINKEDIN

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
            text = post.get("text", "") or post.get("commentary", "") or post.get("content", "")
            if not text or len(text.split()) < 5:
                skipped += 1
                continue

            likes = post.get("likes", 0) or post.get("numLikes", 0)
            comments_count = post.get("comments", 0) or post.get("numComments", 0)
            shares = post.get("shares", 0) or post.get("numShares", 0)

            author_data = post.get("author", {})
            author_name = (
                author_data.get("name", "")
                or author_data.get("firstName", "")
                or post.get("author_name", "")
            )
            author_title = author_data.get("headline", "") or author_data.get("title", "")

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="post",
                exact_quote=True,
                source_url=post.get("url") or post.get("shareUrl"),
                source_id=post.get("id") or post.get("urn"),
                author=author_name,
                timestamp=post.get("publishedAt") or post.get("created_at"),
                engagement={
                    "likes": likes,
                    "comments": comments_count,
                    "shares": shares,
                },
                platform_metadata={
                    "author_title": author_title,
                    "author_followers": author_data.get("followers", 0),
                    "post_type": post.get("type", "text"),
                    "is_article": post.get("type") == "article",
                    "hashtags": post.get("hashtags", []),
                },
            ))

        # ── Extract from comments ──
        for comment in comments:
            text = comment.get("text", "") or comment.get("comment", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            commenter = comment.get("author", {})
            commenter_name = commenter.get("name", "") or comment.get("author_name", "")
            commenter_title = commenter.get("headline", "") or commenter.get("title", "")

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_id=comment.get("id"),
                author=commenter_name,
                timestamp=comment.get("created_at") or comment.get("publishedAt"),
                engagement={
                    "likes": comment.get("likes", 0) or comment.get("numLikes", 0),
                },
                platform_metadata={
                    "commenter_title": commenter_title,
                    "is_reply": bool(comment.get("parent_id")),
                },
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(posts) + len(comments),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

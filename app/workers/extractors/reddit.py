"""Reddit post and comment extractor.

Knows Reddit's unique structure: subreddit context matters enormously,
upvote ratio signals consensus, comment threading reveals debate,
and Reddit users are often more detailed/technical than other platforms.
Reddit comments are the highest-quality VOC source for many categories.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class RedditExtractor(BaseExtractor):
    platform = SourcePlatform.REDDIT

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

        # ── Extract from posts ──
        for post in posts:
            data = post.get("data", post)
            title = data.get("title", "")
            selftext = data.get("selftext", "")
            subreddit = data.get("subreddit", "")

            if title:
                payloads.append(ExtractionPayload(
                    content=title,
                    source_platform=self.platform,
                    extraction_type="post_title",
                    exact_quote=True,
                    source_url=f"https://reddit.com{data.get('permalink', '')}",
                    source_id=data.get("id"),
                    author=data.get("author"),
                    timestamp=str(data.get("created_utc", "")),
                    engagement={
                        "score": data.get("score", 0),
                        "upvote_ratio": data.get("upvote_ratio", 0),
                        "comments": data.get("num_comments", 0),
                        "awards": data.get("total_awards_received", 0),
                    },
                    platform_metadata={
                        "subreddit": subreddit,
                        "flair": data.get("link_flair_text"),
                        "is_self": data.get("is_self", True),
                        # Reddit-specific: high upvote ratio = strong consensus
                        "consensus_signal": (
                            "strong" if data.get("upvote_ratio", 0) > 0.9
                            else "moderate" if data.get("upvote_ratio", 0) > 0.7
                            else "contested"
                        ),
                    },
                    suggested_category="pain" if any(w in title.lower() for w in ["help", "problem", "issue", "frustrated"]) else None,
                ))

            if selftext and len(selftext) > 20 and selftext != "[removed]":
                payloads.append(ExtractionPayload(
                    content=selftext,
                    source_platform=self.platform,
                    extraction_type="post_body",
                    exact_quote=True,
                    source_url=f"https://reddit.com{data.get('permalink', '')}",
                    source_id=data.get("id"),
                    author=data.get("author"),
                    platform_metadata={"subreddit": subreddit},
                ))

        # ── Extract from comments ──
        for comment in comments:
            data = comment.get("data", comment)
            body = data.get("body", "")

            if not body or len(body.split()) < 5 or body in ("[removed]", "[deleted]"):
                skipped += 1
                continue

            score = data.get("score", 0)

            payloads.append(ExtractionPayload(
                content=body,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_url=f"https://reddit.com{data.get('permalink', '')}",
                source_id=data.get("id"),
                author=data.get("author"),
                timestamp=str(data.get("created_utc", "")),
                engagement={
                    "score": score,
                    "awards": data.get("total_awards_received", 0),
                    "is_gilded": data.get("gilded", 0) > 0,
                },
                platform_metadata={
                    "subreddit": data.get("subreddit"),
                    "depth": data.get("depth", 0),
                    "is_submitter": data.get("is_submitter", False),
                    "controversiality": data.get("controversiality", 0),
                    # Reddit-specific: highly-upvoted comments represent consensus
                    "quality_signal": (
                        "high" if score > 50
                        else "medium" if score > 10
                        else "low"
                    ),
                },
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(posts) + len(comments),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

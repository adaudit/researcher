"""YouTube comment, video description, and ad extractor.

Knows YouTube's data structure: threaded comments with reply chains,
video descriptions with timestamps, chapters, community posts, and
YouTube-specific engagement patterns (comments are higher intent than
likes on YouTube vs other platforms).
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class YouTubeExtractor(BaseExtractor):
    platform = SourcePlatform.YOUTUBE

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        comments = raw_data.get("comments", [])
        videos = raw_data.get("videos", [])

        # ── Extract from comments ──
        for comment in comments:
            snippet = comment.get("snippet", {})
            top_level = snippet.get("topLevelComment", {}).get("snippet", snippet)

            text = top_level.get("textDisplay", "") or top_level.get("textOriginal", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            # Strip HTML tags from YouTube comments
            import re
            clean_text = re.sub(r"<[^>]+>", "", text).strip()
            if not clean_text:
                skipped += 1
                continue

            payloads.append(ExtractionPayload(
                content=clean_text,
                source_platform=self.platform,
                extraction_type="comment",
                exact_quote=True,
                source_url=f"https://youtube.com/watch?v={top_level.get('videoId')}",
                source_id=comment.get("id"),
                author=top_level.get("authorDisplayName"),
                timestamp=top_level.get("publishedAt"),
                engagement={
                    "likes": top_level.get("likeCount", 0),
                    "replies": snippet.get("totalReplyCount", 0),
                },
                platform_metadata={
                    "video_id": top_level.get("videoId"),
                    "is_reply": "parentId" in top_level,
                    "is_hearted": top_level.get("viewerRating") == "like",
                    # YT-specific: comments with replies are higher-signal
                    "has_creator_reply": any(
                        r.get("snippet", {}).get("authorChannelId") == raw_data.get("channel_id")
                        for r in comment.get("replies", {}).get("comments", [])
                    ),
                },
            ))

        # ── Extract from video descriptions ──
        for video in videos:
            snippet = video.get("snippet", {})
            desc = snippet.get("description", "")
            title = snippet.get("title", "")

            if title:
                payloads.append(ExtractionPayload(
                    content=title,
                    source_platform=self.platform,
                    extraction_type="headline",
                    source_url=f"https://youtube.com/watch?v={video.get('id')}",
                    source_id=video.get("id"),
                    timestamp=snippet.get("publishedAt"),
                    engagement={
                        "views": video.get("statistics", {}).get("viewCount"),
                        "likes": video.get("statistics", {}).get("likeCount"),
                        "comments": video.get("statistics", {}).get("commentCount"),
                    },
                    suggested_category="hook",
                ))

            if desc and len(desc) > 20:
                payloads.append(ExtractionPayload(
                    content=desc,
                    source_platform=self.platform,
                    extraction_type="video_description",
                    source_url=f"https://youtube.com/watch?v={video.get('id')}",
                    source_id=video.get("id"),
                    timestamp=snippet.get("publishedAt"),
                    platform_metadata={
                        "tags": snippet.get("tags", []),
                        "category": snippet.get("categoryId"),
                        "duration": video.get("contentDetails", {}).get("duration"),
                    },
                ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(comments) + len(videos),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

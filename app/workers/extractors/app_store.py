"""App Store extractor — review title, body, rating, version, device.

App Store-specific: reviews tied to specific app versions reveal which
updates caused satisfaction or frustration. Rating distribution over
time shows product trajectory. Developer responses indicate active
customer care.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class AppStoreExtractor(BaseExtractor):
    platform = SourcePlatform.APP_STORE

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        reviews = raw_data.get("reviews", [])
        if isinstance(raw_data, list):
            reviews = raw_data

        for review in reviews:
            title = review.get("title", "")
            body = review.get("body", "") or review.get("content", "") or review.get("text", "")
            rating = review.get("rating", 0) or review.get("score", 0)

            if not body or len(body.split()) < 3:
                if not title:
                    skipped += 1
                    continue

            content = f"{title}: {body}" if title and body else (body or title)

            author_name = review.get("userName", "") or review.get("author", "") or review.get("reviewer", "")
            version = review.get("version", "") or review.get("app_version", "")

            # Category hints
            suggested = None
            if rating <= 2:
                suggested = "pain"
            elif rating >= 4 and len(body.split()) > 15:
                suggested = "desire"  # What they love = what they desired

            payloads.append(ExtractionPayload(
                content=content,
                source_platform=self.platform,
                extraction_type="review",
                exact_quote=True,
                confidence=0.85,
                source_url=review.get("url"),
                source_id=review.get("id") or review.get("reviewId"),
                author=author_name,
                timestamp=review.get("date") or review.get("updated") or review.get("created_at"),
                engagement={
                    "rating": rating,
                    "vote_count": review.get("voteCount", 0) or review.get("helpful", 0),
                },
                platform_metadata={
                    "rating": rating,
                    "title": title,
                    "version": version,
                    "device": review.get("device", ""),
                    "country": review.get("country", "") or review.get("territory", ""),
                    "has_developer_response": bool(
                        review.get("developerResponse") or review.get("developer_reply")
                    ),
                },
                suggested_category=suggested,
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(reviews),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

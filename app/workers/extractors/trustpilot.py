"""Trustpilot extractor — review title, body, rating, verified status.

Trustpilot-specific: verified reviews carry more weight, star rating
distribution reveals satisfaction patterns, review titles are often
the most emotionally charged and make great hook raw material.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class TrustpilotExtractor(BaseExtractor):
    platform = SourcePlatform.TRUSTPILOT

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
            body = review.get("text", "") or review.get("body", "") or review.get("content", "")
            rating = review.get("rating", 0) or review.get("stars", 0)

            # Skip empty or very short reviews
            if not body or len(body.split()) < 3:
                if not title:
                    skipped += 1
                    continue

            # Combine title and body for content
            content = f"{title}: {body}" if title and body else (body or title)

            is_verified = bool(
                review.get("isVerified")
                or review.get("verified")
                or review.get("verification_status") == "verified"
            )

            author_data = review.get("consumer", {}) or review.get("author", {})
            author_name = (
                author_data.get("displayName", "")
                or author_data.get("name", "")
                or review.get("author_name", "")
            )

            # Category hints based on rating
            suggested = None
            if rating <= 2:
                suggested = "objection"  # Negative reviews reveal objections
            elif rating >= 4 and len(body.split()) > 20:
                suggested = "proof"  # Detailed positive reviews are social proof

            payloads.append(ExtractionPayload(
                content=content,
                source_platform=self.platform,
                extraction_type="review",
                exact_quote=True,
                confidence=0.9 if is_verified else 0.7,
                source_url=review.get("url") or review.get("links", {}).get("review"),
                source_id=review.get("id"),
                author=author_name,
                timestamp=review.get("createdAt") or review.get("created_at") or review.get("date"),
                engagement={
                    "rating": rating,
                    "useful_count": review.get("usefulCount", 0) or review.get("helpful", 0),
                },
                platform_metadata={
                    "rating": rating,
                    "is_verified": is_verified,
                    "title": title,
                    "review_count_by_author": author_data.get("numberOfReviews", 0),
                    "reply_from_business": bool(review.get("businessReply") or review.get("reply")),
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

"""Amazon product review extractor.

Knows Amazon's review structure: verified purchase badges, star ratings,
helpful votes, review titles (often the best VOC), vine reviews,
and the critical difference between recent reviews and top reviews.
Amazon reviews are the single richest source for product-specific VOC.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class AmazonReviewExtractor(BaseExtractor):
    platform = SourcePlatform.AMAZON_REVIEWS

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

        for review in reviews:
            title = review.get("title", "")
            body = review.get("body", "") or review.get("text", "")
            rating = review.get("rating", 0) or review.get("stars", 0)

            # Review title — often the most concentrated VOC
            if title and len(title) > 5:
                payloads.append(ExtractionPayload(
                    content=title,
                    source_platform=self.platform,
                    extraction_type="review_title",
                    exact_quote=True,
                    source_url=review.get("url"),
                    source_id=review.get("id"),
                    author=review.get("author_name"),
                    timestamp=review.get("date"),
                    engagement={
                        "helpful_votes": review.get("helpful_votes", 0),
                        "rating": rating,
                    },
                    platform_metadata={
                        "verified_purchase": review.get("verified_purchase", False),
                        "vine": review.get("vine_review", False),
                        "rating": rating,
                        "product_asin": review.get("asin"),
                    },
                    suggested_category=_suggest_from_rating(rating),
                ))

            # Review body
            if body and len(body.split()) >= 5:
                payloads.append(ExtractionPayload(
                    content=body,
                    source_platform=self.platform,
                    extraction_type="review_body",
                    exact_quote=True,
                    source_url=review.get("url"),
                    source_id=review.get("id"),
                    author=review.get("author_name"),
                    timestamp=review.get("date"),
                    engagement={
                        "helpful_votes": review.get("helpful_votes", 0),
                        "rating": rating,
                    },
                    platform_metadata={
                        "verified_purchase": review.get("verified_purchase", False),
                        "rating": rating,
                        "has_images": bool(review.get("images")),
                        "has_video": bool(review.get("videos")),
                        # Amazon-specific: verified + helpful = gold-standard VOC
                        "quality_signal": (
                            "gold" if review.get("verified_purchase") and review.get("helpful_votes", 0) > 5
                            else "high" if review.get("verified_purchase")
                            else "standard"
                        ),
                    },
                    suggested_category=_suggest_from_rating(rating),
                ))
            else:
                skipped += 1

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(reviews),
            extracted_count=len(payloads),
            skipped_count=skipped,
            metadata={
                "rating_distribution": _rating_distribution(reviews),
            },
        )


def _suggest_from_rating(rating: int | float) -> str | None:
    if rating <= 2:
        return "pain"
    if rating >= 4:
        return "desire"
    return None


def _rating_distribution(reviews: list[dict]) -> dict[str, int]:
    dist: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for r in reviews:
        stars = str(int(r.get("rating", 0) or r.get("stars", 0)))
        if stars in dist:
            dist[stars] += 1
    return dist

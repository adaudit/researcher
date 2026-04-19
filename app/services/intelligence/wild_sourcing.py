"""Wild sourcing — fetch real images from the wild internet (SCRAWLS "W").

Goes OUTSIDE the advertising ecosystem to find native, authentic,
UGC-quality reference images from:
  - Reddit (subreddits relevant to the audience)
  - Unsplash / Pexels (free stock but filtered for authentic look)
  - ScrapCreators for platform-native images

These images serve as:
  1. Style references for AI image generation (Midjourney with reference)
  2. Mood boards for creative direction
  3. "What real content looks like" calibration

The goal is NOT polished stock photos. It's images that look like
someone actually took them — the kind of thing you'd scroll past
and think "is this an ad? ...no wait, it's just a post."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.storage.object_store import object_store

logger = logging.getLogger(__name__)


@dataclass
class WildImage:
    """A reference image found in the wild."""

    url: str
    source: str              # reddit | unsplash | pexels | forum | social
    description: str
    subreddit: str | None = None
    relevance_reason: str = ""
    native_quality_score: int = 0   # 1-10, how native/authentic it looks
    stored_key: str | None = None   # S3 key if downloaded


class WildSourcingService:
    """Fetches authentic reference images from the wild internet."""

    async def search_reddit_images(
        self,
        keywords: list[str],
        subreddits: list[str] | None = None,
        *,
        max_results: int = 30,
    ) -> list[WildImage]:
        """Search Reddit for images relevant to the audience/product.

        Looks for:
        - Image posts with high engagement in relevant subreddits
        - UGC-quality photos (not memes, not screenshots)
        - Content that FEELS real and native

        Good subreddits for reference images:
        - Pain/problem subs: r/ChronicPain, r/insomnia, r/backpain
        - Identity subs: r/fitness, r/1200isplenty, r/skincare
        - Product-adjacent: r/supplements, r/Nootropics
        - Visual reference: r/itookapicture, r/AccidentalRenaissance
        """
        images: list[WildImage] = []

        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

            all_subreddits = subreddits or []
            for keyword in keywords:
                # Search across Reddit
                result = await scrapecreators_client.reddit.search_posts(
                    query=keyword,
                    limit=max_results,
                )

                for post in result.data:
                    # Filter for image posts
                    url = post.get("url", "")
                    is_image = any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])
                    preview = post.get("preview", {})
                    if preview and not is_image:
                        images_list = preview.get("images", [])
                        if images_list:
                            url = images_list[0].get("source", {}).get("url", "")
                            is_image = bool(url)

                    if not is_image:
                        continue

                    score = post.get("score", 0)
                    if score < 10:
                        continue

                    images.append(WildImage(
                        url=url,
                        source="reddit",
                        description=post.get("title", ""),
                        subreddit=post.get("subreddit", ""),
                        relevance_reason=f"Keyword match: {keyword}",
                        native_quality_score=7,  # Reddit images are typically authentic
                    ))

        except Exception as exc:
            logger.warning("wild_sourcing.reddit_failed error=%s", exc)

        return images[:max_results]

    async def search_organic_platform_images(
        self,
        keywords: list[str],
        platforms: list[str] | None = None,
        *,
        max_results: int = 20,
    ) -> list[WildImage]:
        """Search social platforms for native-looking images.

        Pulls from TikTok, Instagram etc. via ScrapCreators,
        looking for organic (non-ad) content with authentic visual style.
        """
        images: list[WildImage] = []
        platforms = platforms or ["tiktok", "instagram"]

        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

            for keyword in keywords:
                for platform in platforms:
                    if platform == "tiktok":
                        result = await scrapecreators_client.tiktok.search_videos(
                            query=keyword, count=10,
                        )
                        for item in result.data:
                            thumbnail = item.get("cover", "") or item.get("thumbnail", "")
                            if thumbnail:
                                images.append(WildImage(
                                    url=thumbnail,
                                    source=f"tiktok_organic",
                                    description=item.get("desc", "")[:200],
                                    native_quality_score=8,
                                ))

                    elif platform == "instagram":
                        result = await scrapecreators_client.instagram.search_hashtag(
                            hashtag=keyword, count=10,
                        )
                        for item in result.data:
                            img_url = item.get("image_url", "") or item.get("display_url", "")
                            if img_url:
                                images.append(WildImage(
                                    url=img_url,
                                    source="instagram_organic",
                                    description=item.get("caption", "")[:200],
                                    native_quality_score=8,
                                ))

        except Exception as exc:
            logger.warning("wild_sourcing.platform_failed error=%s", exc)

        return images[:max_results]

    async def search_web_images(
        self,
        query: str,
        *,
        max_results: int = 20,
    ) -> list[WildImage]:
        """Search the web for reference images via Scrapling.

        Falls back to web search for image results when
        platform-specific APIs don't cover the concept.
        """
        images: list[WildImage] = []

        try:
            from app.services.acquisition.connectors.web_scraper import web_scraper

            results = await web_scraper.search_web(query=f"{query} photo", max_results=max_results)
            for r in results:
                if any(ext in r.url.lower() for ext in [".jpg", ".png", ".webp", "image"]):
                    images.append(WildImage(
                        url=r.url,
                        source="web_search",
                        description=r.title,
                        native_quality_score=5,  # Web search images vary in authenticity
                    ))

        except Exception as exc:
            logger.warning("wild_sourcing.web_failed error=%s", exc)

        return images[:max_results]

    async def build_reference_library(
        self,
        account_id: str,
        offer_id: str | None,
        keywords: list[str],
        *,
        subreddits: list[str] | None = None,
        max_total: int = 60,
    ) -> dict[str, Any]:
        """Build a wild sourcing reference library for an account.

        Pulls from all sources, retains as seeds, and returns
        the full set of wild images found.
        """
        all_images: list[WildImage] = []

        # Reddit images
        reddit_images = await self.search_reddit_images(
            keywords, subreddits, max_results=30,
        )
        all_images.extend(reddit_images)

        # Organic platform images
        platform_images = await self.search_organic_platform_images(
            keywords, max_results=20,
        )
        all_images.extend(platform_images)

        # Web search images
        for keyword in keywords[:3]:
            web_images = await self.search_web_images(keyword, max_results=10)
            all_images.extend(web_images)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[WildImage] = []
        for img in all_images:
            if img.url not in seen_urls:
                seen_urls.add(img.url)
                unique.append(img)

        unique = unique[:max_total]

        # Retain as seeds
        for img in unique:
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.SEEDS,
                content=(
                    f"Wild image reference ({img.source}): {img.description}. "
                    f"URL: {img.url}. "
                    f"Native quality: {img.native_quality_score}/10."
                ),
                offer_id=offer_id,
                source_type="wild_sourcing",
                evidence_type="visual_reference",
                confidence_score=0.5,
                extra_metadata={
                    "seed_source": "wild",
                    "image_url": img.url,
                    "source_platform": img.source,
                    "native_score": img.native_quality_score,
                },
            )

        logger.info(
            "wild_sourcing.complete account=%s images=%d sources=%s",
            account_id, len(unique),
            ", ".join(set(img.source for img in unique)),
        )

        return {
            "total_found": len(unique),
            "by_source": {
                source: len([i for i in unique if i.source == source])
                for source in set(i.source for i in unique)
            },
            "images": [
                {
                    "url": img.url,
                    "source": img.source,
                    "description": img.description,
                    "native_score": img.native_quality_score,
                }
                for img in unique
            ],
        }


# Module-level singleton
wild_sourcing = WildSourcingService()

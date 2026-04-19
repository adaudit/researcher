"""ScrapCreators API client — unified social platform data acquisition.

Single async client wrapping the ScrapCreators REST API. Covers 27+ platforms
(TikTok, Instagram, YouTube, Reddit, Twitter/X, Facebook, LinkedIn, Threads, etc.)
through 110+ endpoints with one API key.

Usage:
    client = ScrapCreatorsClient()
    ads = await client.tiktok.search_ads("grounding sheets", country="US", limit=20)
    comments = await client.youtube.get_comments("dQw4w9WgXcQ", limit=50)
    posts = await client.reddit.search_posts("supplements", subreddit="Nootropics", limit=30)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default base URL — ScrapCreators REST API
_BASE_URL = "https://api.scrapecreators.com/v1"


@dataclass
class PaginatedResponse:
    """Standardized paginated response from any ScrapCreators endpoint."""

    data: list[dict[str, Any]]
    total: int
    has_more: bool
    cursor: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class _PlatformNamespace:
    """Base class for platform-specific endpoint groups."""

    def __init__(self, client: ScrapCreatorsClient, platform: str) -> None:
        self._client = client
        self._platform = platform

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._client._request("GET", f"/{self._platform}/{endpoint}", params=params)

    async def _post(self, endpoint: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._client._request("POST", f"/{self._platform}/{endpoint}", json_body=body)

    def _paginated(self, raw: dict[str, Any]) -> PaginatedResponse:
        """Normalize any ScrapCreators response into PaginatedResponse."""
        # ScrapCreators may use different keys — normalize
        data = raw.get("data") or raw.get("results") or raw.get("items") or []
        if isinstance(data, dict):
            data = [data]
        return PaginatedResponse(
            data=data,
            total=raw.get("total", len(data)),
            has_more=raw.get("has_more", False) or raw.get("hasMore", False),
            cursor=raw.get("cursor") or raw.get("next_cursor"),
            raw_response=raw,
        )


# ── TikTok ─────────────────────────────────────────────────────────────


class TikTokNamespace(_PlatformNamespace):
    """TikTok endpoints — ads, videos, comments, profiles, trending."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "tiktok")

    async def search_ads(
        self,
        keyword: str,
        *,
        country: str = "US",
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search TikTok Creative Center / Ad Library for ads by keyword."""
        params: dict[str, Any] = {"keyword": keyword, "country": country, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("ads/search", params))

    async def get_ad_details(self, ad_id: str) -> dict[str, Any]:
        """Get detailed info for a specific TikTok ad."""
        return await self._get(f"ads/{ad_id}")

    async def get_video_comments(
        self,
        video_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Fetch comments on a TikTok video."""
        params: dict[str, Any] = {"video_id": video_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("comments", params))

    async def get_video_details(self, video_id: str) -> dict[str, Any]:
        """Get video metadata, stats, and description."""
        return await self._get(f"videos/{video_id}")

    async def search_videos(
        self,
        keyword: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search TikTok videos by keyword."""
        params: dict[str, Any] = {"keyword": keyword, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("videos/search", params))

    async def get_user_videos(
        self,
        username: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get recent videos from a TikTok user."""
        params: dict[str, Any] = {"username": username, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("users/videos", params))

    async def get_trending(
        self, *, country: str = "US", limit: int = 20
    ) -> PaginatedResponse:
        """Get trending TikTok content."""
        return self._paginated(await self._get("trending", {"country": country, "limit": limit}))


# ── YouTube ────────────────────────────────────────────────────────────


class YouTubeNamespace(_PlatformNamespace):
    """YouTube endpoints — videos, comments, channels, search."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "youtube")

    async def get_comments(
        self,
        video_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Fetch comments on a YouTube video."""
        params: dict[str, Any] = {"video_id": video_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("comments", params))

    async def get_video_details(self, video_id: str) -> dict[str, Any]:
        """Get video metadata, stats, description."""
        return await self._get(f"videos/{video_id}")

    async def search_videos(
        self,
        query: str,
        *,
        limit: int = 20,
        order: str = "relevance",
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search YouTube videos."""
        params: dict[str, Any] = {"query": query, "limit": limit, "order": order}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("videos/search", params))

    async def get_channel_videos(
        self,
        channel_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get recent videos from a YouTube channel."""
        params: dict[str, Any] = {"channel_id": channel_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("channels/videos", params))


# ── Reddit ─────────────────────────────────────────────────────────────


class RedditNamespace(_PlatformNamespace):
    """Reddit endpoints — posts, comments, subreddit search."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "reddit")

    async def search_posts(
        self,
        query: str,
        *,
        subreddit: str | None = None,
        sort: str = "relevance",
        limit: int = 25,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search Reddit posts, optionally within a subreddit."""
        params: dict[str, Any] = {"query": query, "sort": sort, "limit": limit}
        if subreddit:
            params["subreddit"] = subreddit
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("posts/search", params))

    async def get_post_comments(
        self,
        post_id: str,
        *,
        limit: int = 50,
        sort: str = "best",
    ) -> PaginatedResponse:
        """Fetch comments on a Reddit post."""
        params: dict[str, Any] = {"post_id": post_id, "limit": limit, "sort": sort}
        return self._paginated(await self._get("comments", params))

    async def get_subreddit_posts(
        self,
        subreddit: str,
        *,
        sort: str = "hot",
        limit: int = 25,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get posts from a subreddit."""
        params: dict[str, Any] = {"subreddit": subreddit, "sort": sort, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("subreddits/posts", params))


# ── Meta / Facebook ────────────────────────────────────────────────────


class MetaNamespace(_PlatformNamespace):
    """Meta/Facebook endpoints — Ad Library, page posts, comments."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "facebook")

    async def search_ad_library(
        self,
        query: str,
        *,
        country: str = "US",
        ad_type: str = "all",
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search Meta Ad Library for active ads."""
        params: dict[str, Any] = {
            "query": query,
            "country": country,
            "ad_type": ad_type,
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("ads/search", params))

    async def get_ad_details(self, ad_id: str) -> dict[str, Any]:
        """Get detailed info for a specific Meta ad."""
        return await self._get(f"ads/{ad_id}")

    async def get_page_posts(
        self,
        page_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get recent posts from a Facebook page."""
        params: dict[str, Any] = {"page_id": page_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("pages/posts", params))

    async def get_post_comments(
        self,
        post_id: str,
        *,
        limit: int = 50,
    ) -> PaginatedResponse:
        """Fetch comments on a Facebook post."""
        return self._paginated(await self._get("comments", {"post_id": post_id, "limit": limit}))


# ── Instagram ──────────────────────────────────────────────────────────


class InstagramNamespace(_PlatformNamespace):
    """Instagram endpoints — posts, comments, profiles, reels."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "instagram")

    async def get_post_comments(
        self,
        post_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Fetch comments on an Instagram post."""
        params: dict[str, Any] = {"post_id": post_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("comments", params))

    async def get_user_posts(
        self,
        username: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get recent posts from an Instagram user."""
        params: dict[str, Any] = {"username": username, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("users/posts", params))

    async def search_hashtag(
        self,
        hashtag: str,
        *,
        limit: int = 20,
    ) -> PaginatedResponse:
        """Search Instagram posts by hashtag."""
        return self._paginated(await self._get("hashtags/posts", {"hashtag": hashtag, "limit": limit}))


# ── Twitter/X ──────────────────────────────────────────────────────────


class TwitterNamespace(_PlatformNamespace):
    """Twitter/X endpoints — tweets, search, profiles, replies."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "twitter")

    async def search_tweets(
        self,
        query: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search Twitter/X for tweets."""
        params: dict[str, Any] = {"query": query, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("tweets/search", params))

    async def get_tweet_replies(
        self,
        tweet_id: str,
        *,
        limit: int = 50,
    ) -> PaginatedResponse:
        """Fetch replies to a tweet."""
        return self._paginated(
            await self._get("tweets/replies", {"tweet_id": tweet_id, "limit": limit})
        )

    async def get_user_tweets(
        self,
        username: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Get recent tweets from a user."""
        params: dict[str, Any] = {"username": username, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("users/tweets", params))


# ── LinkedIn ───────────────────────────────────────────────────────────


class LinkedInNamespace(_PlatformNamespace):
    """LinkedIn endpoints — posts, comments, company profiles."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "linkedin")

    async def search_posts(
        self,
        query: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Search LinkedIn posts."""
        params: dict[str, Any] = {"query": query, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("posts/search", params))

    async def get_post_comments(
        self,
        post_id: str,
        *,
        limit: int = 50,
    ) -> PaginatedResponse:
        """Fetch comments on a LinkedIn post."""
        return self._paginated(await self._get("comments", {"post_id": post_id, "limit": limit}))

    async def get_company_posts(
        self,
        company_id: str,
        *,
        limit: int = 20,
    ) -> PaginatedResponse:
        """Get recent posts from a LinkedIn company page."""
        return self._paginated(
            await self._get("companies/posts", {"company_id": company_id, "limit": limit})
        )


# ── Threads ────────────────────────────────────────────────────────────


class ThreadsNamespace(_PlatformNamespace):
    """Threads endpoints — posts, replies, profiles."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "threads")

    async def get_user_posts(
        self,
        username: str,
        *,
        limit: int = 20,
    ) -> PaginatedResponse:
        """Get recent posts from a Threads user."""
        return self._paginated(
            await self._get("users/posts", {"username": username, "limit": limit})
        )

    async def get_post_replies(
        self,
        post_id: str,
        *,
        limit: int = 50,
    ) -> PaginatedResponse:
        """Fetch replies to a Threads post."""
        return self._paginated(
            await self._get("posts/replies", {"post_id": post_id, "limit": limit})
        )


# ── Amazon ─────────────────────────────────────────────────────────────


class AmazonNamespace(_PlatformNamespace):
    """Amazon endpoints — product reviews, search."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "amazon")

    async def get_product_reviews(
        self,
        asin: str,
        *,
        country: str = "US",
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Fetch reviews for an Amazon product by ASIN."""
        params: dict[str, Any] = {"asin": asin, "country": country, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("reviews", params))

    async def search_products(
        self,
        query: str,
        *,
        country: str = "US",
        limit: int = 20,
    ) -> PaginatedResponse:
        """Search Amazon products."""
        return self._paginated(
            await self._get("products/search", {"query": query, "country": country, "limit": limit})
        )


# ── Trustpilot ─────────────────────────────────────────────────────────


class TrustpilotNamespace(_PlatformNamespace):
    """Trustpilot endpoints — company reviews."""

    def __init__(self, client: ScrapCreatorsClient) -> None:
        super().__init__(client, "trustpilot")

    async def get_company_reviews(
        self,
        domain: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> PaginatedResponse:
        """Fetch reviews for a company by domain."""
        params: dict[str, Any] = {"domain": domain, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._paginated(await self._get("reviews", params))


# ── Main Client ────────────────────────────────────────────────────────


class ScrapCreatorsClient:
    """Unified social platform data acquisition via ScrapCreators API.

    All 27+ platforms through one interface. Platform namespaces provide
    typed methods for each endpoint group.

    Usage:
        client = ScrapCreatorsClient()
        ads = await client.tiktok.search_ads("grounding sheets")
        comments = await client.youtube.get_comments("dQw4w9WgXcQ")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.SCRAPECREATORS_API_KEY
        self._base_url = (base_url or _BASE_URL).rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "x-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=60.0,
        )

        # Platform namespaces
        self.tiktok = TikTokNamespace(self)
        self.youtube = YouTubeNamespace(self)
        self.reddit = RedditNamespace(self)
        self.meta = MetaNamespace(self)
        self.instagram = InstagramNamespace(self)
        self.twitter = TwitterNamespace(self)
        self.linkedin = LinkedInNamespace(self)
        self.threads = ThreadsNamespace(self)
        self.amazon = AmazonNamespace(self)
        self.trustpilot = TrustpilotNamespace(self)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the ScrapCreators API."""
        logger.info("scrapecreators.%s %s", method, path)
        resp = await self._http.request(method, path, params=params, json=json_body)
        resp.raise_for_status()
        return resp.json()

    async def raw_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Escape hatch for endpoints not yet wrapped in a namespace.

        ScrapCreators has 110+ endpoints — this lets you call any of them
        directly while we add typed wrappers incrementally.
        """
        return await self._request(method, path, params=params, json_body=json_body)

    async def close(self) -> None:
        await self._http.aclose()


# Module-level singleton
scrapecreators_client = ScrapCreatorsClient()

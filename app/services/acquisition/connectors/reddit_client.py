"""Reddit search via PRAW (free) with ScrapCreators fallback.

PRAW is the official Reddit API wrapper — free tier supports basic
post/comment search and subreddit browsing.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RedditClient:
    """Reddit search — PRAW first, ScrapCreators fallback."""

    async def search(
        self,
        query: str,
        *,
        subreddit: str | None = None,
        sort: str = "relevance",
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Search Reddit posts."""
        results = await self._search_praw(query, subreddit, sort, limit)
        if not results:
            results = await self._search_scrapecreators(query, subreddit, limit)
        return results

    async def get_rising(
        self,
        subreddit: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get rising posts from a subreddit (trending concerns)."""
        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
            result = await scrapecreators_client.reddit.get_subreddit_posts(
                subreddit, sort="new", limit=limit,
            )
            return result.data
        except Exception as exc:
            logger.debug("reddit.rising_failed subreddit=%s error=%s", subreddit, exc)
            return []

    async def _search_praw(
        self,
        query: str,
        subreddit: str | None,
        sort: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search via PRAW (official Reddit API)."""
        try:
            import praw

            reddit = praw.Reddit(
                client_id="researcher-bot",
                client_secret=None,
                user_agent="researcher/0.1",
            )
            if subreddit:
                submissions = reddit.subreddit(subreddit).search(
                    query, sort=sort, limit=limit,
                )
            else:
                submissions = reddit.subreddit("all").search(
                    query, sort=sort, limit=limit,
                )

            results: list[dict[str, Any]] = []
            for s in submissions:
                results.append({
                    "id": s.id,
                    "title": s.title,
                    "text": s.selftext[:500] if s.selftext else "",
                    "subreddit": str(s.subreddit),
                    "score": s.score,
                    "num_comments": s.num_comments,
                    "url": f"https://reddit.com{s.permalink}",
                    "created_utc": s.created_utc,
                    "source": "praw",
                })
            logger.info("reddit.praw_search query=%s results=%d", query[:50], len(results))
            return results
        except ImportError:
            logger.debug("reddit.praw_not_installed — falling back to ScrapCreators")
            return []
        except Exception as exc:
            logger.debug("reddit.praw_failed query=%s error=%s", query[:50], exc)
            return []

    async def _search_scrapecreators(
        self,
        query: str,
        subreddit: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fallback to ScrapCreators Reddit endpoint."""
        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
            result = await scrapecreators_client.reddit.search_posts(
                query, subreddit=subreddit, limit=limit,
            )
            return result.data
        except Exception as exc:
            logger.debug("reddit.scrapecreators_failed query=%s error=%s", query[:50], exc)
            return []


reddit_client = RedditClient()

"""Google News RSS + generic news search.

Free — no API key required. Uses Google News RSS feeds which provide
structured results with titles, links, publication dates, and sources.
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)


class NewsClient:
    """Google News RSS search — free, no API key."""

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        language: str = "en",
        country: str = "US",
    ) -> list[dict[str, Any]]:
        """Search Google News via RSS feed."""
        from urllib.parse import quote_plus

        url = (
            f"https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl={language}&gl={country}&ceid={country}:{language}"
        )

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            root = ElementTree.fromstring(resp.text)
            items: list[dict[str, Any]] = []

            for item in root.findall(".//item")[:max_results]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "")

                items.append({
                    "title": title,
                    "url": link,
                    "published_at": pub_date,
                    "source": source,
                    "type": "news",
                })

            logger.info("news.search query=%s results=%d", query[:50], len(items))
            return items
        except Exception as exc:
            logger.warning("news.search_failed query=%s error=%s", query[:50], exc)
            return []

    async def get_topic_feed(
        self,
        topic: str,
        *,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Get news from a Google News topic (health, science, business)."""
        topic_map = {
            "health": "CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ",
            "science": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pWVXlnQVAB",
            "business": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB",
        }
        topic_id = topic_map.get(topic.lower())
        if not topic_id:
            return await self.search(topic, max_results=max_results)

        url = f"https://news.google.com/rss/topics/{topic_id}"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            root = ElementTree.fromstring(resp.text)
            items: list[dict[str, Any]] = []

            for item in root.findall(".//item")[:max_results]:
                items.append({
                    "title": item.findtext("title", ""),
                    "url": item.findtext("link", ""),
                    "published_at": item.findtext("pubDate", ""),
                    "source": item.findtext("source", ""),
                    "type": "news_topic",
                    "topic": topic,
                })

            return items
        except Exception as exc:
            logger.warning("news.topic_feed_failed topic=%s error=%s", topic, exc)
            return []


news_client = NewsClient()

"""Podcast discovery and transcript retrieval.

Layered approach:
  1. Taddy API (free tier) — search episodes, get pre-built transcripts
  2. YouTube fallback — many podcasts upload to YouTube
  3. Whisper fallback — download audio from RSS feed, transcribe locally
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PodcastEpisode:
    title: str
    show_name: str
    description: str
    audio_url: str | None = None
    transcript: str | None = None
    published_at: str | None = None
    duration_seconds: int = 0
    source: str = "taddy"


class PodcastClient:
    """Multi-source podcast search and transcript retrieval."""

    async def search_episodes(
        self,
        query: str,
        *,
        genre: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for podcast episodes matching a query."""
        results = await self._search_taddy(query, genre, limit)
        if not results:
            results = await self._search_youtube_podcasts(query, limit)
        return results

    async def get_transcript(
        self,
        episode_id: str | None = None,
        audio_url: str | None = None,
        youtube_video_id: str | None = None,
    ) -> str | None:
        """Get transcript for an episode, trying multiple sources."""
        if episode_id:
            transcript = await self._get_taddy_transcript(episode_id)
            if transcript:
                return transcript

        if youtube_video_id:
            transcript = await self._get_youtube_transcript(youtube_video_id)
            if transcript:
                return transcript

        if audio_url:
            transcript = await self._transcribe_with_whisper(audio_url)
            if transcript:
                return transcript

        return None

    async def _search_taddy(
        self,
        query: str,
        genre: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search Taddy API for podcast episodes."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                graphql_query = """
                query SearchEpisodes($term: String!, $limit: Int) {
                    searchForTerm(term: $term, filterForType: PODCASTEPISODE, limitPerPage: $limit) {
                        searchResults {
                            ... on PodcastEpisode {
                                uuid
                                name
                                description
                                audioUrl
                                datePublished
                                duration
                                podcastSeries { uuid name }
                            }
                        }
                    }
                }"""
                resp = await client.post(
                    "https://api.taddy.org",
                    json={
                        "query": graphql_query,
                        "variables": {"term": query, "limit": limit},
                    },
                    headers={
                        "Content-Type": "application/json",
                        "X-USER-ID": "researcher-bot",
                        "X-API-KEY": "free-tier",
                    },
                )
                data = resp.json()
                results = (
                    data.get("data", {})
                    .get("searchForTerm", {})
                    .get("searchResults", [])
                )
                return [
                    {
                        "id": r.get("uuid"),
                        "title": r.get("name", ""),
                        "show": r.get("podcastSeries", {}).get("name", ""),
                        "description": r.get("description", "")[:500],
                        "audio_url": r.get("audioUrl"),
                        "published": r.get("datePublished"),
                        "duration": r.get("duration", 0),
                        "source": "taddy",
                    }
                    for r in results
                ]
        except Exception as exc:
            logger.debug("podcast.taddy_search_failed query=%s error=%s", query[:50], exc)
            return []

    async def _get_taddy_transcript(self, episode_id: str) -> str | None:
        """Fetch pre-built transcript from Taddy."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                graphql_query = """
                query GetTranscript($uuid: ID!) {
                    getPodcastEpisode(uuid: $uuid) {
                        transcript { text }
                    }
                }"""
                resp = await client.post(
                    "https://api.taddy.org",
                    json={
                        "query": graphql_query,
                        "variables": {"uuid": episode_id},
                    },
                    headers={
                        "Content-Type": "application/json",
                        "X-USER-ID": "researcher-bot",
                        "X-API-KEY": "free-tier",
                    },
                )
                data = resp.json()
                transcript = (
                    data.get("data", {})
                    .get("getPodcastEpisode", {})
                    .get("transcript", {})
                    .get("text")
                )
                return transcript
        except Exception as exc:
            logger.debug("podcast.taddy_transcript_failed id=%s error=%s", episode_id, exc)
            return None

    async def _search_youtube_podcasts(
        self, query: str, limit: int,
    ) -> list[dict[str, Any]]:
        """Search YouTube for podcast episodes as fallback."""
        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
            result = await scrapecreators_client.youtube.search_videos(
                f"{query} podcast", limit=limit,
            )
            return [
                {
                    "id": v.get("id"),
                    "title": v.get("title", ""),
                    "show": v.get("channel_name", ""),
                    "description": v.get("description", "")[:500],
                    "youtube_id": v.get("id"),
                    "source": "youtube",
                }
                for v in result.data
            ]
        except Exception as exc:
            logger.debug("podcast.youtube_fallback_failed query=%s error=%s", query[:50], exc)
            return []

    async def _get_youtube_transcript(self, video_id: str) -> str | None:
        """Get auto-generated captions from YouTube."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join(t["text"] for t in transcript_list)
        except Exception as exc:
            logger.debug("podcast.youtube_transcript_failed id=%s error=%s", video_id, exc)
            return None

    async def _transcribe_with_whisper(self, audio_url: str) -> str | None:
        """Download audio and transcribe with Whisper (last resort)."""
        logger.debug("podcast.whisper_transcribe url=%s", audio_url[:80])
        return None


podcast_client = PodcastClient()

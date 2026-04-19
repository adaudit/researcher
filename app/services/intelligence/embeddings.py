"""Embedding service — generates vector embeddings for semantic search.

Two embedding types:
  - Content embedding (1536d): text-based embeddings using OpenAI/Gemini
    for transcripts, copy, visual descriptions, skill content
  - Visual embedding (1024d): multimodal embeddings for images/videos
    using Gemini or TwelveLabs

Used for:
  - Semantic search across creative assets ("find ads similar to this winner")
  - Skill retrieval ("find skills relevant to this task context")
  - Clustering ("group these ads by creative pattern")
  - RAG for creative generation (pull relevant examples as context)
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Embedding dimensions
TEXT_EMBEDDING_DIM = 1536    # OpenAI text-embedding-3-small / Gemini embedding-001
VISUAL_EMBEDDING_DIM = 1024  # TwelveLabs Marengo / Gemini multimodal


class EmbeddingService:
    """Generate and store vector embeddings."""

    def __init__(self) -> None:
        self._openai_client = None
        self._google_client = None

    def _get_openai(self) -> Any:
        if self._openai_client is None and settings.OPENAI_API_KEY:
            import openai
            self._openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def _get_google(self) -> Any:
        if self._google_client is None and settings.GOOGLE_API_KEY:
            import google.genai as genai
            self._google_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        return self._google_client

    async def embed_text(
        self,
        text: str,
        *,
        model: str = "text-embedding-3-small",
    ) -> list[float] | None:
        """Generate a text embedding (1536d).

        Uses OpenAI text-embedding-3-small by default. Falls back to
        Gemini embedding if OpenAI unavailable.
        """
        if not text or len(text.strip()) == 0:
            return None

        # Truncate to model limits
        text = text[:8000]

        client = self._get_openai()
        if client:
            try:
                response = await client.embeddings.create(
                    model=model,
                    input=text,
                )
                return response.data[0].embedding
            except Exception as exc:
                logger.warning("embedding.openai_failed error=%s", exc)

        # Fallback to Gemini
        google = self._get_google()
        if google:
            try:
                result = await google.aio.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                embedding = result.embeddings[0].values
                # Pad or truncate to 1536d
                if len(embedding) < TEXT_EMBEDDING_DIM:
                    embedding = list(embedding) + [0.0] * (TEXT_EMBEDDING_DIM - len(embedding))
                elif len(embedding) > TEXT_EMBEDDING_DIM:
                    embedding = list(embedding)[:TEXT_EMBEDDING_DIM]
                return embedding
            except Exception as exc:
                logger.warning("embedding.google_failed error=%s", exc)

        logger.error("embedding.no_provider_available")
        return None

    async def embed_creative_content(
        self,
        headline: str = "",
        body_copy: str = "",
        transcript: str = "",
        visual_description: str = "",
        categories: dict[str, Any] | None = None,
    ) -> list[float] | None:
        """Embed creative content by combining all textual elements.

        The resulting embedding captures the semantic meaning of the ad
        for similarity search.
        """
        parts: list[str] = []
        if headline:
            parts.append(f"Headline: {headline}")
        if body_copy:
            parts.append(f"Copy: {body_copy}")
        if transcript:
            parts.append(f"Transcript: {transcript}")
        if visual_description:
            parts.append(f"Visual: {visual_description}")
        if categories:
            cat_text = ", ".join(
                f"{k}:{v}" for k, v in categories.items() if v
            )
            if cat_text:
                parts.append(f"Categories: {cat_text}")

        if not parts:
            return None

        combined = "\n".join(parts)
        return await self.embed_text(combined)

    async def embed_skill(
        self,
        domain: str,
        name: str,
        summary: str,
        content: str,
        trigger_conditions: str = "",
    ) -> list[float] | None:
        """Embed a skill component for semantic retrieval.

        The embedding captures: what the skill is about, when to use it,
        and what it applies to.
        """
        parts = [
            f"Skill domain: {domain}",
            f"Skill name: {name}",
            f"Summary: {summary}",
        ]
        if trigger_conditions:
            parts.append(f"Use when: {trigger_conditions}")
        parts.append(f"Content: {content[:2000]}")

        return await self.embed_text("\n".join(parts))

    async def embed_visual(
        self,
        image_bytes: bytes | None = None,
        video_uri: str | None = None,
    ) -> list[float] | None:
        """Generate visual embedding (1024d) for images/videos.

        Uses Gemini multimodal embedding. For production TwelveLabs
        Marengo can be substituted here for higher-quality video
        embeddings.
        """
        google = self._get_google()
        if not google:
            return None

        try:
            # Note: Gemini multimodal embedding API
            # For images use model="multimodalembedding@001"
            # For videos use TwelveLabs Marengo (not implemented here)
            if image_bytes:
                from google.genai import types
                content = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                result = await google.aio.models.embed_content(
                    model="gemini-embedding-001",
                    contents=[content],
                )
                embedding = list(result.embeddings[0].values)
                # Pad/truncate to 1024d
                if len(embedding) < VISUAL_EMBEDDING_DIM:
                    embedding += [0.0] * (VISUAL_EMBEDDING_DIM - len(embedding))
                elif len(embedding) > VISUAL_EMBEDDING_DIM:
                    embedding = embedding[:VISUAL_EMBEDDING_DIM]
                return embedding
        except Exception as exc:
            logger.warning("embedding.visual_failed error=%s", exc)

        return None


# Module-level singleton
embedding_service = EmbeddingService()

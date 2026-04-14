"""Multi-provider LLM router.

Routes tasks to the best model for each capability:
  - Claude (Anthropic): strategic reasoning, writing analysis, structured synthesis
  - Gemini (Google): video analysis, image understanding, long-context documents
  - GPT (OpenAI): function calling, fast structured extraction

Each task declares a Capability, and the router selects the best
provider + model for that capability. Providers can be disabled
via config if API keys are missing.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class Capability(str, Enum):
    """What the task needs the model to be good at."""

    # Reasoning and strategy
    STRATEGIC_REASONING = "strategic_reasoning"   # desire maps, differentiation, hooks
    COPY_ANALYSIS = "copy_analysis"               # copy police, compression tax
    SYNTHESIS = "synthesis"                        # briefs, iteration planning
    REFLECTION = "reflection"                     # memory reflection, lesson extraction

    # Extraction
    TEXT_EXTRACTION = "text_extraction"            # structured data from text
    CLASSIFICATION = "classification"             # categorization, sentiment

    # Multimodal
    VIDEO_ANALYSIS = "video_analysis"             # video understanding, scene analysis
    IMAGE_ANALYSIS = "image_analysis"             # screenshot analysis, ad creative review
    LONG_DOCUMENT = "long_document"               # full page HTML, long transcripts

    # Generation
    CREATIVE_GENERATION = "creative_generation"   # hook writing, angle generation


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"


# ── Capability → Provider routing table ─────────────────────────────
# Best provider for each capability based on benchmarks and strengths.
# Falls back through the list if a provider is unavailable.

CAPABILITY_ROUTING: dict[Capability, list[tuple[Provider, str]]] = {
    # Claude excels at nuanced reasoning and writing analysis
    Capability.STRATEGIC_REASONING: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.GOOGLE, "gemini-2.5-pro"),
        (Provider.OPENAI, "o3"),
    ],
    Capability.COPY_ANALYSIS: [
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
        (Provider.OPENAI, "gpt-4.1"),
        (Provider.GOOGLE, "gemini-2.5-flash"),
    ],
    Capability.SYNTHESIS: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.GOOGLE, "gemini-2.5-pro"),
    ],
    Capability.REFLECTION: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.GOOGLE, "gemini-2.5-pro"),
    ],

    # Gemini excels at multimodal: video, images, long documents
    Capability.VIDEO_ANALYSIS: [
        (Provider.GOOGLE, "gemini-2.5-pro"),
        (Provider.OPENAI, "gpt-4.1"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
    ],
    Capability.IMAGE_ANALYSIS: [
        (Provider.GOOGLE, "gemini-2.5-pro"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
        (Provider.OPENAI, "gpt-4.1"),
    ],
    Capability.LONG_DOCUMENT: [
        (Provider.GOOGLE, "gemini-2.5-flash"),    # 1M context
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),  # 200K context
    ],

    # Fast extraction — price-optimized
    Capability.TEXT_EXTRACTION: [
        (Provider.ANTHROPIC, "claude-haiku-4-5-20251001"),
        (Provider.GOOGLE, "gemini-2.5-flash"),
        (Provider.OPENAI, "gpt-4.1-mini"),
    ],
    Capability.CLASSIFICATION: [
        (Provider.ANTHROPIC, "claude-haiku-4-5-20251001"),
        (Provider.GOOGLE, "gemini-2.5-flash"),
        (Provider.OPENAI, "gpt-4.1-mini"),
    ],

    # Creative generation — benefits from higher temperature + strong writing
    Capability.CREATIVE_GENERATION: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.GOOGLE, "gemini-2.5-pro"),
        (Provider.OPENAI, "o3"),
    ],
}


class ModelRouter:
    """Routes tasks to the best available model per capability."""

    def __init__(self) -> None:
        self._providers: dict[Provider, Any] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize available providers based on configured API keys."""
        # Anthropic
        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self._providers[Provider.ANTHROPIC] = anthropic.AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY,
                )
                logger.info("router.provider_ready provider=anthropic")
            except ImportError:
                logger.warning("router.anthropic_sdk_missing")

        # Google
        if settings.GOOGLE_API_KEY:
            try:
                import google.genai as genai
                self._providers[Provider.GOOGLE] = genai.Client(
                    api_key=settings.GOOGLE_API_KEY,
                )
                logger.info("router.provider_ready provider=google")
            except ImportError:
                logger.warning("router.google_sdk_missing")

        # OpenAI
        if settings.OPENAI_API_KEY:
            try:
                import openai
                self._providers[Provider.OPENAI] = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                )
                logger.info("router.provider_ready provider=openai")
            except ImportError:
                logger.warning("router.openai_sdk_missing")

        if not self._providers:
            logger.error("router.no_providers_available — at least one API key required")

    def resolve(self, capability: Capability) -> tuple[Provider, str]:
        """Pick the best available provider + model for a capability."""
        routes = CAPABILITY_ROUTING.get(capability, [])
        for provider, model in routes:
            if provider in self._providers:
                return provider, model

        # Fallback: use any available provider with a reasonable model
        for provider in self._providers:
            if provider == Provider.ANTHROPIC:
                return provider, "claude-sonnet-4-6"
            if provider == Provider.GOOGLE:
                return provider, "gemini-2.5-flash"
            if provider == Provider.OPENAI:
                return provider, "gpt-4.1-mini"

        raise RuntimeError("No LLM providers available")

    async def generate(
        self,
        *,
        capability: Capability,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_schema: dict[str, Any] | None = None,
        context_documents: list[str] | None = None,
        images: list[bytes] | None = None,
        video_uri: str | None = None,
    ) -> dict[str, Any]:
        """Generate a response using the best model for the capability.

        Args:
            capability: What the task needs the model to do well.
            system_prompt: Worker-specific instructions.
            user_prompt: Task-specific input.
            temperature: Creativity control.
            max_tokens: Response budget.
            json_schema: Forces structured JSON output.
            context_documents: Large docs for cache breakpoints (Anthropic).
            images: Image bytes for multimodal analysis.
            video_uri: Video URI for Gemini video analysis.
        """
        provider, model = self.resolve(capability)

        logger.info(
            "router.generate capability=%s provider=%s model=%s",
            capability.value, provider.value, model,
        )

        if json_schema:
            user_prompt += (
                "\n\nRespond with valid JSON matching this schema. "
                "No markdown fences, no explanation:\n"
                f"{json.dumps(json_schema, indent=2)}"
            )

        if provider == Provider.ANTHROPIC:
            return await self._generate_anthropic(
                model, system_prompt, user_prompt, temperature, max_tokens,
                context_documents, images,
            )
        elif provider == Provider.GOOGLE:
            return await self._generate_google(
                model, system_prompt, user_prompt, temperature, max_tokens,
                images, video_uri,
            )
        elif provider == Provider.OPENAI:
            return await self._generate_openai(
                model, system_prompt, user_prompt, temperature, max_tokens,
                images,
            )

        raise ValueError(f"Unknown provider: {provider}")

    # ── Provider implementations ────────────────────────────────────

    async def _generate_anthropic(
        self, model: str, system: str, user: str,
        temperature: float, max_tokens: int,
        context_docs: list[str] | None, images: list[bytes] | None,
    ) -> dict[str, Any]:
        client = self._providers[Provider.ANTHROPIC]

        # System blocks with cache control
        system_blocks = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        if context_docs:
            for doc in context_docs:
                system_blocks.append(
                    {"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}
                )

        # Build user content (text + optional images)
        user_content: list[dict[str, Any]] = []
        if images:
            import base64
            for img in images:
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(img).decode(),
                    },
                })
        user_content.append({"type": "text", "text": user})

        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user_content}],
        )

        usage = response.usage
        logger.info(
            "anthropic.usage model=%s input=%d output=%d cache_create=%d cache_read=%d",
            model, usage.input_tokens, usage.output_tokens,
            getattr(usage, "cache_creation_input_tokens", 0),
            getattr(usage, "cache_read_input_tokens", 0),
        )

        return _parse_json(response.content[0].text)

    async def _generate_google(
        self, model: str, system: str, user: str,
        temperature: float, max_tokens: int,
        images: list[bytes] | None, video_uri: str | None,
    ) -> dict[str, Any]:
        client = self._providers[Provider.GOOGLE]
        from google.genai import types

        contents: list[Any] = []

        # Add video if provided (Gemini's strength)
        if video_uri:
            contents.append(types.Part.from_uri(file_uri=video_uri, mime_type="video/mp4"))

        # Add images if provided
        if images:
            for img in images:
                contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))

        contents.append(user)

        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )

        logger.info(
            "google.usage model=%s input=%d output=%d",
            model,
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )

        return _parse_json(response.text)

    async def _generate_openai(
        self, model: str, system: str, user: str,
        temperature: float, max_tokens: int,
        images: list[bytes] | None,
    ) -> dict[str, Any]:
        client = self._providers[Provider.OPENAI]

        messages = [
            {"role": "system", "content": system},
        ]

        # Build user message with optional images
        if images:
            import base64
            content: list[dict[str, Any]] = []
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64.b64encode(img).decode()}",
                    },
                })
            content.append({"type": "text", "text": user})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user})

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        usage = response.usage
        logger.info(
            "openai.usage model=%s input=%d output=%d",
            model, usage.prompt_tokens, usage.completion_tokens,
        )

        return _parse_json(response.choices[0].message.content)


def _parse_json(text: str) -> dict[str, Any]:
    """Extract JSON from model response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        logger.warning("llm.json_parse_failed text=%s", cleaned[:200])
        return {"raw_text": text, "_parse_error": True}


# Module-level singleton
router = ModelRouter()

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
from contextvars import ContextVar
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Per-task trace buffer — when a worker calls start_trace_capture(),
# every router.generate() call inside that async task records its
# capability/provider/model/prompts/response here. BaseWorker reads
# the buffer after execute() and ships it to the training collector.
#
# This replaces the per-worker `_llm_trace` stash pattern. Workers
# don't need to manually capture — the router does it automatically.
_trace_buffer: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "llm_trace_buffer", default=None,
)


def start_trace_capture() -> None:
    """Begin capturing LLM traces in the current async task."""
    _trace_buffer.set([])


def pop_traces() -> list[dict[str, Any]]:
    """Return and clear traces captured in the current async task."""
    buf = _trace_buffer.get()
    if buf is None:
        return []
    _trace_buffer.set(None)
    return buf


def _record_trace(
    capability: Capability,
    provider: Provider,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: dict[str, Any],
) -> None:
    """Append a trace to the active buffer if capture is enabled."""
    buf = _trace_buffer.get()
    if buf is None:
        return
    parse_failed = bool(response.get("_parse_error"))
    buf.append({
        "capability": capability.value,
        "provider": provider.value,
        "model": model,
        "system_prompt": system_prompt[:8000],
        "user_prompt": user_prompt[:8000],
        "response": json.dumps(response, default=str)[:8000],
        "quality_score": 0 if parse_failed else 1,
    })


class Capability(str, Enum):
    """What the task needs the model to be good at."""

    # Reasoning and strategy
    STRATEGIC_REASONING = "strategic_reasoning"   # desire maps, differentiation, coverage
    COPY_ANALYSIS = "copy_analysis"               # copy police, compression tax
    SYNTHESIS = "synthesis"                        # iteration planning
    REFLECTION = "reflection"                     # memory reflection, lesson extraction

    # Extraction
    TEXT_EXTRACTION = "text_extraction"            # structured data from text
    CLASSIFICATION = "classification"             # categorization, sentiment

    # Multimodal
    VIDEO_ANALYSIS = "video_analysis"             # video understanding, scene analysis
    IMAGE_ANALYSIS = "image_analysis"             # screenshot analysis, ad creative review
    LONG_DOCUMENT = "long_document"               # full page HTML, long transcripts

    # Generation — split by copy type per benchmark data
    CREATIVE_GENERATION = "creative_generation"   # general fallback
    LONG_FORM_COPY = "long_form_copy"             # VSL scripts, long-form ads, nuanced prose
    DR_COPY = "dr_copy"                           # direct response, email, landing page, structured
    HOOK_GENERATION = "hook_generation"            # hooks, headlines, punchy short-form
    CONCEPT_GENERATION = "concept_generation"      # image concepts, visual directions


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"
    ZAI = "zai"      # Z.ai GLM-5.1 — OpenAI-compatible API
    XAI = "xai"      # xAI Grok — hooks/headlines, X-corpus-trained
    LOCAL = "local"   # Ollama/vLLM — Gemma 4, Llama, etc.


# ── Capability → Provider routing table ─────────────────────────────
#
# Cost tiers (per million tokens, input/output):
#
#   TIER 0  LOCAL (Gemma 4 26B via Ollama)        $0 / $0
#   TIER 1  Gemini Flash                          $0.15 / $0.60
#   TIER 2  GLM-5.1 (Z.ai API)                   $0.95 / $3.15
#   TIER 3  Sonnet                                $3.00 / $15.00
#   TIER 4  Opus                                  $15.00 / $75.00
#
# Strategy:
#   - Opus ONLY for copy/hook/headline/brief generation (writing IS the product)
#   - GLM-5.1 for all reasoning/analysis (16x cheaper than Opus, #1 SWE-Bench)
#   - Gemma 4 locally for extraction/classification ($0 marginal cost)
#   - Gemini Flash for multimodal + long docs (cheapest with 1M context)
#
# Each list is a fallback chain — first available provider wins.

# ── Capability → Provider routing table ─────────────────────────────
#
# Cost tiers (per million tokens, input/output, April 2026):
#
#   TIER 0  LOCAL (Gemma 4 via Ollama/vLLM)        $0 / $0
#   TIER 1  Gemini 3 Flash                         $0.50 / $3
#   TIER 2  DeepSeek V4 / Qwen 3.5 Flash           $0.065-$0.30 / $0.26-$0.50
#   TIER 3  GLM-5.1 (Z.ai)                         $0.95 / $3.15
#   TIER 4  Grok 4 (xAI)                           $3 / $15
#   TIER 5  GPT-5.4 (OpenAI)                       $2.50 / $10
#   TIER 6  Opus 4.6 (Anthropic)                   $5 / $25
#
# Strategy (by copy type, per benchmark data):
#   - Opus 4.6: long-form copy, nuanced prose (Arena IF: 1500)
#   - GPT-5.4: DR copy, email sequences, structured (IFEval: 96)
#   - Grok 4: hooks, headlines, punchy short-form (bigger swings, X-trained)
#   - Gemini 3.1 Pro: creative boldness at low cost (Arena CW: 1487)
#   - GLM-5.1: reasoning/synthesis (BenchLM 84, NOT final voice)
#   - DeepSeek V4: cheap refinement passes (NOT final voice)
#   - Local/Flash: extraction, classification, high-volume grading

CAPABILITY_ROUTING: dict[Capability, list[tuple[Provider, str]]] = {
    # ── Long-form copy: nuanced prose, VSL scripts, structural coherence ──
    Capability.LONG_FORM_COPY: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.GOOGLE, "gemini-3.1-pro"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── DR copy: email, landing page, structured formats, CTA patterns ──
    Capability.DR_COPY: [
        (Provider.OPENAI, "gpt-5.4"),
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── Hooks/headlines: punchy, irreverent, X-corpus-trained ──
    Capability.HOOK_GENERATION: [
        (Provider.XAI, ""),
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.OPENAI, "gpt-5.4"),
    ],

    # ── Image/visual concepts: creative boldness at low cost ──
    Capability.CONCEPT_GENERATION: [
        (Provider.GOOGLE, "gemini-3.1-pro"),
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── General creative (fallback when specific type not set) ──
    Capability.CREATIVE_GENERATION: [
        (Provider.ANTHROPIC, "claude-opus-4-6"),
        (Provider.OPENAI, "gpt-5.4"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── Reasoning/strategy: NOT customer-facing voice ──
    Capability.STRATEGIC_REASONING: [
        (Provider.ZAI, "glm-5.1"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
        (Provider.GOOGLE, "gemini-3-flash"),
    ],
    Capability.SYNTHESIS: [
        (Provider.ZAI, "glm-5.1"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
        (Provider.GOOGLE, "gemini-3-flash"),
    ],
    Capability.REFLECTION: [
        (Provider.ZAI, "glm-5.1"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
        (Provider.GOOGLE, "gemini-3-flash"),
    ],

    # ── Copy review: mechanical grading, local-first ──
    Capability.COPY_ANALYSIS: [
        (Provider.LOCAL, ""),
        (Provider.GOOGLE, "gemini-3-flash"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── Extraction: high-volume, cheap, local-first ──
    Capability.TEXT_EXTRACTION: [
        (Provider.LOCAL, ""),
        (Provider.GOOGLE, "gemini-3-flash"),
        (Provider.ZAI, "glm-5.1"),
    ],
    Capability.CLASSIFICATION: [
        (Provider.LOCAL, ""),
        (Provider.GOOGLE, "gemini-3-flash"),
        (Provider.ZAI, "glm-5.1"),
    ],

    # ── Multimodal ──
    Capability.VIDEO_ANALYSIS: [
        (Provider.GOOGLE, "gemini-3-flash"),
        (Provider.GOOGLE, "gemini-3.1-pro"),
    ],
    Capability.IMAGE_ANALYSIS: [
        (Provider.GOOGLE, "gemini-3-flash"),
        (Provider.ZAI, "glm-5.1"),
    ],
    Capability.LONG_DOCUMENT: [
        (Provider.GOOGLE, "gemini-3-flash"),        # 1M context
        (Provider.ZAI, "glm-5.1"),                  # 200K context
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),   # 1M context
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

        # Z.ai (GLM-5.1 — OpenAI-compatible API, cheap high-quality reasoning)
        if settings.ZAI_API_KEY:
            try:
                import openai
                self._providers[Provider.ZAI] = openai.AsyncOpenAI(
                    base_url=settings.ZAI_BASE_URL,
                    api_key=settings.ZAI_API_KEY,
                )
                logger.info(
                    "router.provider_ready provider=zai model=%s",
                    settings.ZAI_MODEL,
                )
            except ImportError:
                logger.warning("router.zai_needs_openai_sdk")

        # xAI / Grok (hooks, headlines — OpenAI-compatible API)
        if settings.XAI_API_KEY:
            try:
                import openai
                self._providers[Provider.XAI] = openai.AsyncOpenAI(
                    base_url=settings.XAI_BASE_URL,
                    api_key=settings.XAI_API_KEY,
                )
                logger.info(
                    "router.provider_ready provider=xai model=%s",
                    settings.XAI_MODEL,
                )
            except ImportError:
                logger.warning("router.xai_needs_openai_sdk")

        # Local LLM (Ollama, vLLM — OpenAI-compatible API)
        if settings.LOCAL_LLM_BASE_URL and settings.LOCAL_LLM_MODEL:
            try:
                import openai
                self._providers[Provider.LOCAL] = openai.AsyncOpenAI(
                    base_url=settings.LOCAL_LLM_BASE_URL,
                    api_key="local",  # Most local servers don't need a real key
                )
                logger.info(
                    "router.provider_ready provider=local model=%s url=%s",
                    settings.LOCAL_LLM_MODEL, settings.LOCAL_LLM_BASE_URL,
                )
            except ImportError:
                logger.warning("router.local_needs_openai_sdk")

        if not self._providers:
            logger.error("router.no_providers_available — at least one API key required")

    def resolve(self, capability: Capability) -> tuple[Provider, str]:
        """Pick the best available provider + model for a capability."""
        routes = CAPABILITY_ROUTING.get(capability, [])
        for provider, model in routes:
            if provider in self._providers:
                if provider == Provider.LOCAL:
                    model = settings.LOCAL_LLM_MODEL
                elif provider == Provider.ZAI:
                    model = model or settings.ZAI_MODEL
                elif provider == Provider.XAI:
                    model = settings.XAI_MODEL
                return provider, model

        # Fallback: use any available provider with a reasonable model
        for provider in self._providers:
            if provider == Provider.ZAI:
                return provider, settings.ZAI_MODEL
            if provider == Provider.ANTHROPIC:
                return provider, "claude-sonnet-4-6"
            if provider == Provider.GOOGLE:
                return provider, "gemini-3-flash"
            if provider == Provider.OPENAI:
                return provider, "gpt-5.4"
            if provider == Provider.XAI:
                return provider, settings.XAI_MODEL
            if provider == Provider.LOCAL:
                return provider, settings.LOCAL_LLM_MODEL

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
            response = await self._generate_anthropic(
                model, system_prompt, user_prompt, temperature, max_tokens,
                context_documents, images,
            )
        elif provider == Provider.GOOGLE:
            response = await self._generate_google(
                model, system_prompt, user_prompt, temperature, max_tokens,
                images, video_uri,
            )
        elif provider == Provider.OPENAI:
            response = await self._generate_openai(
                model, system_prompt, user_prompt, temperature, max_tokens,
                images,
            )
        elif provider == Provider.ZAI:
            response = await self._generate_openai_compat(
                Provider.ZAI, model, system_prompt, user_prompt,
                temperature, max_tokens,
            )
        elif provider == Provider.XAI:
            response = await self._generate_openai_compat(
                Provider.XAI, model, system_prompt, user_prompt,
                temperature, max_tokens,
            )
        elif provider == Provider.LOCAL:
            response = await self._generate_openai_compat(
                Provider.LOCAL, model, system_prompt, user_prompt,
                temperature, max_tokens,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

        # Record trace for training data capture (no-op if capture not active)
        _record_trace(
            capability, provider, model, system_prompt, user_prompt, response,
        )
        return response

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


    async def _generate_openai_compat(
        self, provider: Provider, model: str, system: str, user: str,
        temperature: float, max_tokens: int,
    ) -> dict[str, Any]:
        """Generate via any OpenAI-compatible API (Z.ai GLM-5.1, Ollama, vLLM).

        Both ZAI and LOCAL providers use the OpenAI SDK under the hood,
        just pointed at different base_url endpoints.
        """
        client = self._providers[provider]

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        usage = response.usage
        logger.info(
            "%s.usage model=%s input=%d output=%d",
            provider.value, model,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
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

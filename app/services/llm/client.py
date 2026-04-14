"""LLM client with prompt caching, model routing, and structured output.

Uses the Anthropic SDK with prompt caching to minimize cost and latency.
Model routing sends extraction tasks to Haiku, synthesis to Sonnet,
and high-stakes strategic reasoning to Opus.

Every call returns structured JSON — no free-form prose parsing.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Route tasks to the right model by cognitive demand."""

    FAST = "fast"          # extraction, classification, simple parsing
    STANDARD = "standard"  # synthesis, analysis, brief composition
    ADVANCED = "advanced"  # strategic reasoning, reflection, novel insight


# Model mapping — update IDs as new versions release
MODEL_MAP: dict[ModelTier, str] = {
    ModelTier.FAST: "claude-haiku-4-5-20251001",
    ModelTier.STANDARD: "claude-sonnet-4-6",
    ModelTier.ADVANCED: "claude-opus-4-6",
}


class LLMClient:
    """Anthropic Claude client with prompt caching and structured output."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.OPENAI_API_KEY or "")
        # Cache for system prompts — prompt caching stores the first
        # large block so repeated calls with the same system prompt
        # get cache hits.
        self._system_cache: dict[str, list[dict]] = {}

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier: ModelTier = ModelTier.STANDARD,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_schema: dict[str, Any] | None = None,
        context_documents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a structured response from Claude.

        Args:
            system_prompt: Worker-specific system instructions.
            user_prompt: The task-specific input.
            tier: Model tier for routing.
            temperature: Creativity control (low for extraction, higher for ideation).
            max_tokens: Response budget.
            json_schema: If provided, forces JSON output matching this schema.
            context_documents: Large documents to include with cache breakpoints.

        Returns:
            Parsed JSON response from the model.
        """
        model = MODEL_MAP[tier]

        # Build system message with cache control for prompt caching
        system_blocks = self._build_system_blocks(system_prompt, context_documents)

        messages = [{"role": "user", "content": user_prompt}]

        # If JSON schema requested, append instruction
        if json_schema:
            schema_instruction = (
                "\n\nYou MUST respond with valid JSON matching this exact schema. "
                "No markdown, no explanation, just the JSON object:\n"
                f"```json\n{json.dumps(json_schema, indent=2)}\n```"
            )
            messages[0]["content"] += schema_instruction

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=messages,
            )

            raw_text = response.content[0].text

            # Log cache performance
            usage = response.usage
            logger.info(
                "llm.generate model=%s tier=%s input_tokens=%d output_tokens=%d "
                "cache_creation=%d cache_read=%d",
                model,
                tier.value,
                usage.input_tokens,
                usage.output_tokens,
                getattr(usage, "cache_creation_input_tokens", 0),
                getattr(usage, "cache_read_input_tokens", 0),
            )

            return self._parse_json_response(raw_text)

        except anthropic.APIError as exc:
            logger.error("llm.api_error model=%s error=%s", model, exc)
            raise

    async def generate_stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier: ModelTier = ModelTier.STANDARD,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> str:
        """Stream a response for long-form generation (briefs, copy).

        Returns the full text (not JSON).
        """
        model = MODEL_MAP[tier]
        system_blocks = self._build_system_blocks(system_prompt)

        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text

    def _build_system_blocks(
        self,
        system_prompt: str,
        context_documents: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build system message blocks with cache breakpoints.

        The system prompt gets a cache breakpoint so repeated calls
        with the same worker prompt get cache hits. Large context
        documents also get breakpoints.
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        if context_documents:
            for doc in context_documents:
                blocks.append({
                    "type": "text",
                    "text": doc,
                    "cache_control": {"type": "ephemeral"},
                })

        return blocks

    @staticmethod
    def _parse_json_response(text: str) -> dict[str, Any]:
        """Extract JSON from model response, handling markdown fences."""
        cleaned = text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
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
llm_client = LLMClient()

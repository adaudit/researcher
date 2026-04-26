"""Document ingester — extracts creative strategy knowledge from docs.

Uses LLM (Gemini LONG_DOCUMENT for big docs, Claude for shorter ones)
to extract principles, frameworks, examples, and anti-patterns into
structured JSON that matches the base_training.py corpus format.

Flow: raw doc → LLM extraction → CorpusEntry → store.save()
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)

# Token threshold for routing to LONG_DOCUMENT (Gemini) vs TEXT_EXTRACTION
_LONG_DOC_CHAR_THRESHOLD = 30_000  # ~7,500 tokens

INGESTION_SYSTEM_PROMPT = """\
You are a creative strategy knowledge extractor. Your job is to read a document
about creative strategy, advertising, copywriting, or marketing and extract
STRUCTURED knowledge that can train other AI workers.

Extract the following categories of knowledge from the document:

1. **Principles**: Core truths or rules the document teaches.
   - Each principle needs: name, description (2-3 sentences), and category
     (creative_strategy | copywriting | research | ideation | iteration)

2. **Frameworks**: Structured processes or mental models.
   - Each framework needs: name, description, steps (ordered list), and
     when_to_use guidance

3. **Examples**: Concrete good/bad examples that calibrate quality.
   - Each example needs: context, good_version, bad_version (if available),
     and why_good_is_better explanation

4. **Anti-patterns**: Common mistakes the document warns against.
   - Each anti-pattern needs: name, description, and what_to_do_instead

5. **Vocabulary**: Domain-specific terms and their precise definitions.
   - Each term needs: term, definition, usage_context

Return ONLY knowledge that is actionable for creative strategy workers.
Skip biographical info, sales pitches, and filler content.

Respond with valid JSON matching the schema provided.
"""

INGESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source_summary": {"type": "string"},
        "principles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                },
            },
        },
        "frameworks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "when_to_use": {"type": "string"},
                },
            },
        },
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "context": {"type": "string"},
                    "good_version": {"type": "string"},
                    "bad_version": {"type": "string"},
                    "why_good_is_better": {"type": "string"},
                },
            },
        },
        "anti_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "what_to_do_instead": {"type": "string"},
                },
            },
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"},
                    "usage_context": {"type": "string"},
                },
            },
        },
    },
}


@dataclass
class CorpusEntry:
    """One extracted knowledge unit ready for the corpus store."""

    slug: str
    title: str
    source_summary: str
    source_hash: str
    principles: list[dict[str, str]] = field(default_factory=list)
    frameworks: list[dict[str, Any]] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    anti_patterns: list[dict[str, str]] = field(default_factory=list)
    vocabulary: list[dict[str, str]] = field(default_factory=list)
    version: int = 1


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:80].strip("-")


def _content_hash(content: str) -> str:
    """SHA-256 hash of content for dedup and versioning."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def ingest_document(
    content: str,
    *,
    title: str | None = None,
    slug: str | None = None,
) -> CorpusEntry:
    """Ingest a raw document and extract structured creative strategy knowledge.

    Args:
        content: Raw document text (markdown, plain text, or extracted PDF text).
        title: Optional title override. If not provided, LLM will extract one.
        slug: Optional slug override. If not provided, derived from title.

    Returns:
        CorpusEntry ready to be saved to the corpus store.
    """
    content_hash = _content_hash(content)

    # Route long docs to Gemini, shorter ones to Claude extraction
    capability = (
        Capability.LONG_DOCUMENT
        if len(content) > _LONG_DOC_CHAR_THRESHOLD
        else Capability.TEXT_EXTRACTION
    )

    logger.info(
        "doc_ingest.start chars=%d capability=%s",
        len(content),
        capability.value,
    )

    result = await router.generate(
        capability=capability,
        system_prompt=INGESTION_SYSTEM_PROMPT,
        user_prompt=(
            f"Extract structured creative strategy knowledge from this document.\n\n"
            f"DOCUMENT:\n{content}"
        ),
        temperature=0.2,
        max_tokens=8192,
        json_schema=INGESTION_SCHEMA,
    )

    if result.get("_parse_error"):
        logger.error("doc_ingest.parse_failed hash=%s", content_hash)
        raise ValueError("Failed to parse LLM extraction response")

    extracted_title = title or result.get("title", "Untitled Document")
    entry_slug = slug or _slugify(extracted_title)

    entry = CorpusEntry(
        slug=entry_slug,
        title=extracted_title,
        source_summary=result.get("source_summary", ""),
        source_hash=content_hash,
        principles=result.get("principles", []),
        frameworks=result.get("frameworks", []),
        examples=result.get("examples", []),
        anti_patterns=result.get("anti_patterns", []),
        vocabulary=result.get("vocabulary", []),
    )

    logger.info(
        "doc_ingest.complete slug=%s principles=%d frameworks=%d examples=%d",
        entry.slug,
        len(entry.principles),
        len(entry.frameworks),
        len(entry.examples),
    )

    return entry

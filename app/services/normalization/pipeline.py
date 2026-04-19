"""Normalization pipeline — converts raw artifacts into typed,
memory-ready payloads before Hindsight retention.

The pipeline enforces:
  - Source typing: every artifact must declare origin
  - Raw preservation: raw data stored before summarization
  - Deduplication: canonical URL and content hashing
  - Retention threshold: low-quality extractions rejected
  - Provenance linkage: every output links to source artifact
  - Freshness policy: each source type gets its own decay window
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.services.llm.client import ModelTier, llm_client

logger = logging.getLogger(__name__)


# Freshness windows by source type
FRESHNESS_WINDOWS: dict[str, int] = {
    "landing_page": 14,
    "ad_creative": 7,
    "comment_dump": 30,
    "transcript": 60,
    "research_doc": 90,
    "screenshot": 14,
    "upload": 30,
}


@dataclass
class NormalizedPayload:
    """Memory-ready payload with full metadata contract."""

    payload_id: str
    artifact_id: str
    account_id: str
    offer_id: str | None

    # Content
    content: str
    content_type: str  # observation | fact | claim | transcript_segment | research_finding
    content_hash: str

    # Metadata contract
    source_type: str
    source_url: str | None
    evidence_type: str
    confidence_score: float
    freshness_window_days: int
    review_status: str = "pending"
    domain_risk_level: str = "standard"

    # Bank targeting
    target_bank_type: str = ""

    # Extra structured data
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizationResult:
    """Result of normalizing a batch of artifacts."""

    payloads: list[NormalizedPayload]
    rejected: list[dict[str, Any]]
    deduplication_hits: int = 0


class NormalizationPipeline:
    """Converts raw artifacts into memory-ready payloads."""

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    async def normalize_page_capture(
        self,
        *,
        account_id: str,
        offer_id: str | None,
        artifact_id: str,
        url: str,
        text_blocks: list[dict[str, Any]],
        embedded_videos: list[dict[str, Any]],
        meta: dict[str, Any],
    ) -> NormalizationResult:
        """Normalize a landing page capture into memory-ready payloads."""
        payloads: list[NormalizedPayload] = []
        rejected: list[dict[str, Any]] = []
        dedup_hits = 0

        # Use LLM to extract structured observations from page text
        page_text = "\n".join(
            f"[{b.get('tag', 'p')}] {b.get('text', '')}"
            for b in text_blocks if b.get("text")
        )

        if page_text:
            extractions = await self._llm_extract_observations(
                page_text, source_type="landing_page"
            )

            for ext in extractions:
                content = ext.get("content", "")
                content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

                if content_hash in self._seen_hashes:
                    dedup_hits += 1
                    continue
                self._seen_hashes.add(content_hash)

                confidence = ext.get("confidence", 0.5)
                if confidence < 0.4:
                    rejected.append({"content": content[:100], "reason": "below_threshold"})
                    continue

                payloads.append(NormalizedPayload(
                    payload_id=f"np_{uuid4().hex[:8]}",
                    artifact_id=artifact_id,
                    account_id=account_id,
                    offer_id=offer_id,
                    content=content,
                    content_type=ext.get("type", "observation"),
                    content_hash=content_hash,
                    source_type="crawler",
                    source_url=url,
                    evidence_type=ext.get("evidence_type", "landing_page_claim"),
                    confidence_score=confidence,
                    freshness_window_days=FRESHNESS_WINDOWS["landing_page"],
                    target_bank_type="pages",
                    extra_metadata={"section": ext.get("section")},
                ))

        return NormalizationResult(
            payloads=payloads,
            rejected=rejected,
            deduplication_hits=dedup_hits,
        )

    async def normalize_comments(
        self,
        *,
        account_id: str,
        offer_id: str | None,
        artifact_id: str,
        comments: list[str | dict],
        source_url: str = "",
    ) -> NormalizationResult:
        """Normalize raw comments into VOC memory payloads."""
        payloads: list[NormalizedPayload] = []
        rejected: list[dict[str, Any]] = []
        dedup_hits = 0

        comment_texts = [
            c if isinstance(c, str) else c.get("text", "")
            for c in comments
        ]
        comment_texts = [c for c in comment_texts if c.strip()]

        for comment in comment_texts:
            content_hash = hashlib.sha256(comment.encode()).hexdigest()[:16]

            if content_hash in self._seen_hashes:
                dedup_hits += 1
                continue
            self._seen_hashes.add(content_hash)

            # Skip very short comments
            if len(comment.split()) < 5:
                rejected.append({"content": comment[:100], "reason": "too_short"})
                continue

            payloads.append(NormalizedPayload(
                payload_id=f"np_{uuid4().hex[:8]}",
                artifact_id=artifact_id,
                account_id=account_id,
                offer_id=offer_id,
                content=comment,
                content_type="observation",
                content_hash=content_hash,
                source_type="upload",
                source_url=source_url,
                evidence_type="voc_comment",
                confidence_score=0.7,
                freshness_window_days=FRESHNESS_WINDOWS["comment_dump"],
                target_bank_type="voc",
            ))

        return NormalizationResult(
            payloads=payloads,
            rejected=rejected,
            deduplication_hits=dedup_hits,
        )

    async def normalize_transcript(
        self,
        *,
        account_id: str,
        offer_id: str | None,
        artifact_id: str,
        chunks: list[dict[str, Any]],
        source_url: str = "",
    ) -> NormalizationResult:
        """Normalize transcript chunks into memory payloads."""
        payloads: list[NormalizedPayload] = []

        for chunk in chunks:
            text = chunk.get("text", "")
            if not text.strip():
                continue

            content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            if content_hash in self._seen_hashes:
                continue
            self._seen_hashes.add(content_hash)

            payloads.append(NormalizedPayload(
                payload_id=f"np_{uuid4().hex[:8]}",
                artifact_id=artifact_id,
                account_id=account_id,
                offer_id=offer_id,
                content=f"Transcript [{chunk.get('start', 0):.0f}s-{chunk.get('end', 0):.0f}s]: {text}",
                content_type="transcript_segment",
                content_hash=content_hash,
                source_type="transcript",
                source_url=source_url,
                evidence_type="transcript_highlight",
                confidence_score=0.75,
                freshness_window_days=FRESHNESS_WINDOWS["transcript"],
                target_bank_type="pages",
                extra_metadata={
                    "start": chunk.get("start"),
                    "end": chunk.get("end"),
                },
            ))

        return NormalizationResult(payloads=payloads, rejected=[])

    async def normalize_research(
        self,
        *,
        account_id: str,
        offer_id: str | None,
        artifact_id: str,
        results: list[dict[str, Any]],
    ) -> NormalizationResult:
        """Normalize research results into memory payloads."""
        payloads: list[NormalizedPayload] = []

        for r in results:
            title = r.get("title", "")
            summary = r.get("summary", "")
            url = r.get("url", "")
            content = f"{title}. {summary}".strip()

            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            if content_hash in self._seen_hashes:
                continue
            self._seen_hashes.add(content_hash)

            payloads.append(NormalizedPayload(
                payload_id=f"np_{uuid4().hex[:8]}",
                artifact_id=artifact_id,
                account_id=account_id,
                offer_id=offer_id,
                content=content,
                content_type="research_finding",
                content_hash=content_hash,
                source_type="research",
                source_url=url,
                evidence_type="research_finding",
                confidence_score=0.8,
                freshness_window_days=FRESHNESS_WINDOWS["research_doc"],
                target_bank_type="research",
                domain_risk_level="elevated" if r.get("source") == "pubmed" else "standard",
                extra_metadata=r.get("metadata", {}),
            ))

        return NormalizationResult(payloads=payloads, rejected=[])

    async def _llm_extract_observations(
        self,
        text: str,
        source_type: str,
    ) -> list[dict[str, Any]]:
        """Use LLM to extract structured observations from raw text."""
        try:
            result = await llm_client.generate(
                system_prompt=(
                    "You are a content extraction system. Extract distinct, atomic observations "
                    "from the provided text. Each observation should be a single fact, claim, "
                    "proof element, or notable pattern. Return a JSON array."
                ),
                user_prompt=(
                    f"Extract observations from this {source_type} content.\n\n"
                    f"For each observation, provide:\n"
                    f"- content: the observation text\n"
                    f"- type: observation | claim | proof | pattern\n"
                    f"- evidence_type: landing_page_claim | proof_claim | hook_pattern | mechanism_insight\n"
                    f"- confidence: 0.0-1.0\n"
                    f"- section: which part of the page/content\n\n"
                    f"TEXT:\n{text[:6000]}"
                ),
                tier=ModelTier.FAST,
                temperature=0.1,
                max_tokens=4000,
                json_schema={
                    "type": "object",
                    "properties": {
                        "observations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {"type": "string"},
                                    "type": {"type": "string"},
                                    "evidence_type": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "section": {"type": "string"},
                                },
                            },
                        }
                    },
                },
            )
            return result.get("observations", [])
        except Exception:
            logger.warning("normalization.llm_extraction_failed")
            return []

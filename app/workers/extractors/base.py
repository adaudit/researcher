"""Base extractor contract.

Extractors are SEPARATE from analysts. An extractor's ONLY job is to
pull structured data from a raw source. It does not interpret, synthesize,
or strategize. It produces typed extraction payloads that analysts consume.

This separation matters because:
1. Different sources need different extraction logic (Instagram ≠ Reddit)
2. Extraction can use fast/cheap models; analysis needs advanced reasoning
3. Extraction outputs are verifiable (did you get the data right?)
4. Analysis outputs are judgmental (did you interpret it well?)
5. You can fine-tune an extraction model without affecting analysis quality
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SourcePlatform(str, Enum):
    """Where the raw data comes from."""

    META_ADS = "meta_ads"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    AMAZON_REVIEWS = "amazon_reviews"
    LANDING_PAGE = "landing_page"
    EMAIL = "email"
    GOOGLE_ADS = "google_ads"
    TWITTER_X = "twitter_x"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    THREADS = "threads"
    TRUSTPILOT = "trustpilot"
    APP_STORE = "app_store"
    GENERIC_COMMENTS = "generic_comments"
    DIRECT_UPLOAD = "direct_upload"


@dataclass
class ExtractionPayload:
    """One extracted item — the atomic output of an extractor.

    This is what flows from extractors → analysts. It carries the raw
    extracted content plus enough metadata for the analyst to know
    where it came from and how trustworthy it is.
    """

    content: str                              # the extracted text/data
    source_platform: SourcePlatform
    extraction_type: str                      # comment | review | ad_copy | headline | transcript | claim
    confidence: float = 0.8
    exact_quote: bool = False                 # True if content is exact customer language

    # Source linkage
    source_url: str | None = None
    source_id: str | None = None              # platform-specific ID
    author: str | None = None
    timestamp: str | None = None

    # Platform-specific context
    engagement: dict[str, Any] | None = None  # likes, shares, replies
    platform_metadata: dict[str, Any] = field(default_factory=dict)

    # Classification hints (extractor suggests, analyst decides)
    suggested_category: str | None = None     # desire | pain | objection | hook | claim | proof


@dataclass
class ExtractionResult:
    """Complete output from an extraction run."""

    platform: SourcePlatform
    payloads: list[ExtractionPayload]
    raw_count: int = 0          # how many raw items were processed
    extracted_count: int = 0    # how many payloads were produced
    skipped_count: int = 0      # how many were skipped (too short, duplicate, etc.)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    """Abstract base for all platform-specific extractors.

    Subclasses must implement:
      - platform: which source this handles
      - extract(): pull structured data from raw input
    """

    platform: SourcePlatform

    @abstractmethod
    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        """Extract structured payloads from raw platform data.

        The extractor MUST:
          1. Preserve exact text — never paraphrase
          2. Include platform-specific metadata (engagement, timestamps)
          3. Mark exact quotes as exact_quote=True
          4. Skip low-quality items (too short, spam, irrelevant)
          5. Suggest categories but NOT make strategic judgments
        """

    async def run(self, raw_data: Any, **kwargs) -> ExtractionResult:
        logger.info("extractor.start platform=%s", self.platform.value)
        try:
            result = await self.extract(raw_data, **kwargs)

            # Auto-capture training data if the extractor stashed an LLM trace
            llm_trace = result.metadata.get("_llm_trace")
            if llm_trace:
                try:
                    from app.workers.base import _get_training_collector
                    collector = _get_training_collector()
                    collector.capture(
                        worker_name=f"extractor_{self.platform.value}",
                        capability=llm_trace.get("capability", "extraction"),
                        provider=llm_trace.get("provider", "unknown"),
                        model=llm_trace.get("model", "unknown"),
                        system_prompt=llm_trace.get("system_prompt", ""),
                        user_prompt=llm_trace.get("user_prompt", ""),
                        response=llm_trace.get("response", ""),
                        quality_score=llm_trace.get("quality_score", 0),
                        account_id=kwargs.get("account_id", ""),
                        offer_id=kwargs.get("offer_id"),
                        tags=[f"extractor_{self.platform.value}"],
                    )
                except Exception:
                    logger.debug("training.capture_failed extractor=%s", self.platform.value)

            logger.info(
                "extractor.complete platform=%s extracted=%d skipped=%d",
                self.platform.value,
                result.extracted_count,
                result.skipped_count,
            )
            return result
        except Exception as exc:
            logger.exception("extractor.failed platform=%s", self.platform.value)
            return ExtractionResult(
                platform=self.platform,
                payloads=[],
                errors=[str(exc)],
            )

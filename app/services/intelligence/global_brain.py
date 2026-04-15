"""Cross-business intelligence — the global brain.

Three layers of intelligence:
  1. Base brain — universal creative strategy knowledge (base_training.py)
  2. Per-business brain — what works for THIS account (Hindsight per-account banks)
  3. Cross-business brain — anonymized patterns across ALL accounts (GLOBAL bank)

The cross-business brain learns from every account on the platform.
When a pattern holds across multiple businesses, it gets promoted from
per-account reflection → cross-business pattern → eventually base brain.

This module handles:
  - Aggregating anonymized learnings from per-account reflections
  - Identifying cross-business patterns (what works everywhere)
  - Promoting high-confidence patterns to the global bank
  - Making global intelligence available to all accounts
  - Updating the base brain when patterns are durable enough
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)

# The global bank uses a special "platform" account ID
GLOBAL_ACCOUNT_ID = "_platform_global"

# Minimum accounts confirming a pattern before it's promoted to global
MIN_ACCOUNTS_FOR_PROMOTION = 3

# Minimum confidence for a cross-business pattern
MIN_GLOBAL_CONFIDENCE = 0.8


@dataclass
class CrossBusinessPattern:
    """A pattern observed across multiple businesses."""

    pattern: str
    category: str              # hook_type | visual_style | awareness_tactic | format | angle
    account_count: int         # how many accounts confirm this
    evidence_summary: str
    confidence: float
    vertical: str = "all"      # "supplement", "saas", "ecom", or "all"
    performance_signal: str = ""
    falsifiable_prediction: str = ""


CROSS_BUSINESS_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "category": {"type": "string"},
                    "account_count": {"type": "integer"},
                    "confidence": {"type": "number"},
                    "vertical": {"type": "string"},
                    "evidence_summary": {"type": "string"},
                    "performance_signal": {"type": "string"},
                    "falsifiable_prediction": {"type": "string"},
                },
            },
        },
        "emerging_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "signal": {"type": "string"},
                    "account_count": {"type": "integer"},
                    "needs_more_data": {"type": "boolean"},
                },
            },
        },
    },
}


class CrossBusinessBrain:
    """Manages cross-business intelligence aggregation and retrieval."""

    async def aggregate_reflections(
        self,
        account_ids: list[str],
    ) -> dict[str, Any]:
        """Pull durable lessons from multiple accounts and find cross-business patterns.

        This is the core learning loop:
        1. Recall durable lessons from each account's REFLECTION bank
        2. Anonymize (strip account-specific details)
        3. Find patterns that appear across 3+ accounts
        4. Promote confirmed patterns to the GLOBAL bank
        """
        all_lessons: list[dict[str, Any]] = []

        for account_id in account_ids:
            try:
                bank_id = bank_id_for(account_id, BankType.REFLECTION)
                lessons = await hindsight_client.recall(
                    bank_id=bank_id,
                    query="durable lesson pattern winning strategy what works",
                    top_k=20,
                )
                for lesson in lessons:
                    all_lessons.append({
                        "content": lesson.get("content", ""),
                        "account_id": account_id,
                        "confidence": lesson.get("metadata", {}).get("confidence_score", 0),
                        "evidence_type": lesson.get("metadata", {}).get("evidence_type", ""),
                    })
            except Exception:
                logger.debug("global.recall_failed account=%s", account_id)

        if len(all_lessons) < 5:
            return {"patterns": [], "message": "Insufficient data for cross-business analysis"}

        # Anonymize — remove account-specific identifiers
        anonymized = json.dumps([
            {"insight": l["content"], "confidence": l["confidence"]}
            for l in all_lessons
        ], indent=1, default=str)[:12000]

        # LLM analysis to find cross-business patterns
        result = await router.generate(
            capability=Capability.REFLECTION,
            system_prompt=(
                "You are a Cross-Business Intelligence Analyst. You analyze anonymized "
                "learnings from multiple businesses to find UNIVERSAL patterns.\n\n"
                "Rules:\n"
                "- Only promote patterns confirmed by 3+ businesses\n"
                "- Patterns must be actionable, not observational\n"
                "- Each pattern needs a falsifiable prediction\n"
                "- Categorize: hook_type, visual_style, awareness_tactic, format, angle, "
                "proof_strategy, mechanism_approach\n"
                "- Note which verticals the pattern applies to (all, or specific)\n"
                "- Separate confirmed patterns from emerging signals (< 3 accounts)"
            ),
            user_prompt=(
                f"Analyze {len(all_lessons)} anonymized learnings from "
                f"{len(account_ids)} businesses. Find universal patterns.\n\n"
                f"ANONYMIZED LEARNINGS:\n{anonymized}"
            ),
            temperature=0.2,
            max_tokens=6000,
            json_schema=CROSS_BUSINESS_ANALYSIS_SCHEMA,
        )

        # Retain confirmed patterns to GLOBAL bank
        promoted = 0
        for pattern in result.get("patterns", []):
            if pattern.get("account_count", 0) >= MIN_ACCOUNTS_FOR_PROMOTION:
                await retain_observation(
                    account_id=GLOBAL_ACCOUNT_ID,
                    bank_type=BankType.GLOBAL,
                    content=(
                        f"Cross-business pattern ({pattern.get('category', 'general')}): "
                        f"{pattern.get('pattern', '')}. "
                        f"Confirmed by {pattern.get('account_count', 0)} businesses. "
                        f"Prediction: {pattern.get('falsifiable_prediction', '')}."
                    ),
                    source_type="cross_business_aggregation",
                    evidence_type="global_pattern",
                    confidence_score=pattern.get("confidence", 0.8),
                    extra_metadata={
                        "category": pattern.get("category"),
                        "vertical": pattern.get("vertical", "all"),
                        "account_count": pattern.get("account_count"),
                    },
                )
                promoted += 1

        logger.info(
            "global.aggregation_complete accounts=%d lessons=%d patterns=%d promoted=%d",
            len(account_ids), len(all_lessons),
            len(result.get("patterns", [])), promoted,
        )

        return result

    async def recall_global_intelligence(
        self,
        query: str,
        *,
        category: str | None = None,
        vertical: str | None = None,
        top_k: int = 15,
    ) -> list[dict[str, Any]]:
        """Recall cross-business patterns for use in any account's workers.

        This is how account #500 benefits from learnings of accounts #1-499.
        """
        bank_id = bank_id_for(GLOBAL_ACCOUNT_ID, BankType.GLOBAL)
        metadata_filter: dict[str, Any] = {}
        if category:
            metadata_filter["category"] = category
        if vertical:
            metadata_filter["vertical"] = vertical

        try:
            return await hindsight_client.recall(
                bank_id=bank_id,
                query=query,
                top_k=top_k,
                metadata_filter=metadata_filter if metadata_filter else None,
            )
        except Exception:
            logger.debug("global.recall_failed query=%s", query[:50])
            return []

    async def get_global_context_for_worker(
        self,
        worker_name: str,
        query: str,
        vertical: str | None = None,
    ) -> str:
        """Get formatted global intelligence for injection into worker prompts.

        Returns a text block of cross-business patterns relevant to the
        worker's task, ready for prompt injection alongside base training
        and per-account memory.
        """
        # Map workers to relevant pattern categories
        worker_categories: dict[str, list[str]] = {
            "hook_generator": ["hook_type", "awareness_tactic"],
            "hook_engineer": ["hook_type", "awareness_tactic"],
            "copy_generator": ["format", "angle", "proof_strategy"],
            "headline_generator": ["hook_type"],
            "image_concept_generator": ["visual_style"],
            "image_prompt_generator": ["visual_style"],
            "brief_composer": ["angle", "mechanism_approach"],
            "coverage_matrix": ["format", "angle", "visual_style"],
            "creative_loopback": ["visual_style"],
            "ad_analyzer": ["hook_type", "visual_style", "format", "awareness_tactic"],
        }

        categories = worker_categories.get(worker_name, [])
        all_patterns: list[dict[str, Any]] = []

        for cat in categories:
            patterns = await self.recall_global_intelligence(
                query=query, category=cat, vertical=vertical, top_k=5,
            )
            all_patterns.extend(patterns)

        if not all_patterns:
            # Fallback — general recall
            all_patterns = await self.recall_global_intelligence(
                query=query, vertical=vertical, top_k=10,
            )

        if not all_patterns:
            return ""

        lines = ["## Cross-Business Intelligence (patterns from multiple accounts)\n"]
        for p in all_patterns:
            lines.append(f"- {p.get('content', '')}")

        return "\n".join(lines)


# Module-level singleton
global_brain = CrossBusinessBrain()

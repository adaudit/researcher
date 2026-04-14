"""Primer system — living documents that compound creative intelligence.

Primers are per-offer reference documents that evolve over time:
  - ad_primer: How to write ads for this offer (tone, structure, proof usage)
  - hook_primer: How to write hooks (what works, what doesn't, proven patterns)
  - headline_primer: How to write headlines (length, format, power words)

Primers are stored in the Hindsight PRIMERS bank so they benefit from
the retain/recall/reflect cycle. When iteration_planner finds new winners
or memory_reflection surfaces durable patterns, primers get updated.

Primers are injected into copy_generator, hook_generator, and
headline_generator prompts alongside base training context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client
from app.services.hindsight.memory import retain_observation

logger = logging.getLogger(__name__)


class PrimerType(str, Enum):
    AD = "ad_primer"
    HOOK = "hook_primer"
    HEADLINE = "headline_primer"


@dataclass
class Primer:
    """A living primer document."""

    primer_type: PrimerType
    offer_id: str
    account_id: str
    content: str
    version: int = 1
    memory_id: str | None = None


class PrimerStore:
    """Manages living primer docs via Hindsight memory."""

    async def save(
        self,
        account_id: str,
        offer_id: str,
        primer_type: PrimerType,
        content: str,
    ) -> dict[str, Any]:
        """Save or update a primer. Retains to PRIMERS bank.

        Uses primer_type + offer_id as the dedup key via metadata.
        Each save creates a new memory entry (Hindsight handles versioning
        via the retain/recall cycle — newer entries surface first).
        """
        result = await retain_observation(
            account_id=account_id,
            bank_type=BankType.PRIMERS,
            content=content,
            offer_id=offer_id,
            source_type="primer",
            evidence_type=primer_type.value,
            confidence_score=1.0,
            extra_metadata={
                "primer_type": primer_type.value,
                "offer_id": offer_id,
            },
        )

        logger.info(
            "primer.saved account=%s offer=%s type=%s",
            account_id, offer_id, primer_type.value,
        )
        return result or {}

    async def get(
        self,
        account_id: str,
        offer_id: str,
        primer_type: PrimerType,
    ) -> str | None:
        """Recall the latest version of a primer.

        Queries Hindsight PRIMERS bank filtered by primer_type and offer_id.
        Returns the content of the most recent matching memory.
        """
        bank_id = bank_id_for(account_id, BankType.PRIMERS)
        try:
            results = await hindsight_client.recall(
                bank_id=bank_id,
                query=f"{primer_type.value} for offer {offer_id}",
                top_k=1,
                metadata_filter={
                    "primer_type": primer_type.value,
                    "offer_id": offer_id,
                },
            )
            if results and len(results) > 0:
                return results[0].get("content")
        except Exception:
            logger.debug(
                "primer.recall_failed account=%s offer=%s type=%s",
                account_id, offer_id, primer_type.value,
            )
        return None

    async def list_for_offer(
        self,
        account_id: str,
        offer_id: str,
    ) -> list[dict[str, Any]]:
        """List all primers for an offer."""
        bank_id = bank_id_for(account_id, BankType.PRIMERS)
        primers: list[dict[str, Any]] = []

        for pt in PrimerType:
            try:
                results = await hindsight_client.recall(
                    bank_id=bank_id,
                    query=f"{pt.value} for offer {offer_id}",
                    top_k=1,
                    metadata_filter={
                        "primer_type": pt.value,
                        "offer_id": offer_id,
                    },
                )
                if results and len(results) > 0:
                    primers.append({
                        "primer_type": pt.value,
                        "offer_id": offer_id,
                        "content": results[0].get("content", ""),
                        "memory_id": results[0].get("id"),
                    })
            except Exception:
                continue

        return primers

    async def get_all_for_prompt(
        self,
        account_id: str,
        offer_id: str,
    ) -> str:
        """Load all primers for an offer and format for prompt injection.

        Returns a combined text block suitable for appending to a worker's
        system prompt.
        """
        primers = await self.list_for_offer(account_id, offer_id)
        if not primers:
            return ""

        sections = []
        for p in primers:
            label = p["primer_type"].replace("_", " ").title()
            sections.append(f"## {label}\n\n{p['content']}")

        return "\n\n---\n\n".join(sections)


# Module-level singleton
primer_store = PrimerStore()

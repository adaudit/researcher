"""High-level memory operations that bridge the app layer and Hindsight.

Workers should call these functions — not the raw client — so ingestion
guardrails (deduplication, threshold checks, provenance) are enforced
consistently.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.events import DomainEvent, EventTopic, event_bus
from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client

logger = logging.getLogger(__name__)

# Minimum confidence to retain as durable truth
RETENTION_CONFIDENCE_THRESHOLD = 0.4


async def retain_observation(
    account_id: str,
    bank_type: BankType,
    content: str,
    *,
    offer_id: str | None = None,
    artifact_id: str | None = None,
    source_type: str = "manual",
    source_url: str | None = None,
    evidence_type: str = "observation",
    confidence_score: float = 0.5,
    freshness_window_days: int = 30,
    review_status: str = "pending",
    domain_risk_level: str = "standard",
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Retain a normalized observation into the correct Hindsight bank.

    Enforces ingestion guardrails:
    - Content must not be empty.
    - Confidence must meet retention threshold.
    - Metadata contract fields are always populated.
    - Deduplication by content hash within the bank.

    Returns the Hindsight memory reference, or None if rejected.
    """
    if not content or not content.strip():
        logger.warning("memory.retain_skipped reason=empty_content")
        return None

    if confidence_score < RETENTION_CONFIDENCE_THRESHOLD:
        logger.info(
            "memory.retain_skipped reason=below_threshold score=%.2f",
            confidence_score,
        )
        return None

    bid = bank_id_for(account_id, bank_type, offer_id)
    spec = _bank_type_to_memory_type(bank_type)

    metadata: dict[str, Any] = {
        "account_id": account_id,
        "source_type": source_type,
        "evidence_type": evidence_type,
        "confidence_score": confidence_score,
        "freshness_window_days": freshness_window_days,
        "review_status": review_status,
        "domain_risk_level": domain_risk_level,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
    }
    if offer_id:
        metadata["offer_id"] = offer_id
    if artifact_id:
        metadata["artifact_id"] = artifact_id
    if source_url:
        metadata["source_url"] = source_url
    if extra_metadata:
        metadata.update(extra_metadata)

    result = await hindsight_client.retain(
        bank_id=bid,
        content=content,
        memory_type=spec,
        metadata=metadata,
    )

    await event_bus.publish(
        DomainEvent(
            topic=EventTopic.MEMORY_RETAINED,
            payload={
                "bank_id": bid,
                "memory_ref": result.get("id"),
                "evidence_type": evidence_type,
            },
            account_id=account_id,
            offer_id=offer_id,
        )
    )

    return result


async def recall_for_worker(
    worker_name: str,
    account_id: str,
    query: str,
    *,
    offer_id: str | None = None,
    bank_types: list[BankType] | None = None,
    top_k: int = 20,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Recall memories with scope enforcement.

    If bank_types is not supplied, uses the worker's allowed scope from
    the bank model.
    """
    from app.services.hindsight.banks import recall_scope_for_worker

    if bank_types:
        bank_ids = [bank_id_for(account_id, bt, offer_id) for bt in bank_types]
    else:
        bank_ids = recall_scope_for_worker(worker_name, account_id, offer_id)

    if not bank_ids:
        logger.warning("memory.recall_empty_scope worker=%s", worker_name)
        return []

    return await hindsight_client.recall(
        bank_ids=bank_ids,
        query=query,
        top_k=top_k,
        metadata_filter=metadata_filter,
    )


async def trigger_reflection(
    account_id: str,
    source_bank_types: list[BankType],
    *,
    offer_id: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Trigger a reflection cycle across the specified banks."""
    source_ids = [bank_id_for(account_id, bt, offer_id) for bt in source_bank_types]
    output_bid = bank_id_for(account_id, BankType.REFLECTION)

    result = await hindsight_client.reflect(
        bank_ids=source_ids,
        prompt=prompt,
        output_bank_id=output_bid,
    )

    await event_bus.publish(
        DomainEvent(
            topic=EventTopic.MEMORY_REFLECTION_CREATED,
            payload={
                "source_banks": source_ids,
                "output_bank": output_bid,
                "reflection_id": result.get("id"),
            },
            account_id=account_id,
            offer_id=offer_id,
        )
    )

    return result


def _bank_type_to_memory_type(bank_type: BankType) -> str:
    mapping = {
        BankType.CORE: "world_fact",
        BankType.OFFER: "world_fact",
        BankType.CREATIVE: "experience",
        BankType.LANDING_PAGE: "experience",
        BankType.VOC: "experience",
        BankType.RESEARCH: "world_fact",
        BankType.REFLECTION: "mental_model",
        BankType.SEEDS: "experience",
        BankType.PRIMERS: "world_fact",
        BankType.SKILLS: "mental_model",
        BankType.GLOBAL: "mental_model",
    }
    return mapping.get(bank_type, "world_fact")

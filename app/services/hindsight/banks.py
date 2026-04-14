"""Bank model definitions and provisioning logic.

Maps the bank taxonomy from the blueprint:
  - Account core bank:  stable account truths, positioning
  - Offer bank:         mechanism, price, CTA, proof basis, constraints
  - Creative bank:      winning ads, hook patterns, angles, structures
  - Landing-page bank:  section logic, claims, proof, friction, videos
  - VOC bank:           comments, reviews, objections, desire language
  - Research bank:      news, medical research, competitor developments
  - Reflection bank:    durable lessons, shifts, emerging rules
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.services.hindsight.client import hindsight_client

logger = logging.getLogger(__name__)


class BankType(str, Enum):
    CORE = "core"
    OFFER = "offer"
    CREATIVE = "creatives"
    LANDING_PAGE = "pages"
    VOC = "voc"
    RESEARCH = "research"
    REFLECTION = "reflections"
    SEEDS = "seeds"
    PRIMERS = "primers"


@dataclass(frozen=True)
class BankSpec:
    bank_type: BankType
    description: str
    default_memory_type: str  # world_fact | experience | mental_model


BANK_SPECS: dict[BankType, BankSpec] = {
    BankType.CORE: BankSpec(
        BankType.CORE,
        "Stable account truths, offer context, and positioning",
        "world_fact",
    ),
    BankType.OFFER: BankSpec(
        BankType.OFFER,
        "Mechanism, price, CTA, proof basis, and constraints",
        "world_fact",
    ),
    BankType.CREATIVE: BankSpec(
        BankType.CREATIVE,
        "Winning ads, hook patterns, angles, and structures",
        "experience",
    ),
    BankType.LANDING_PAGE: BankSpec(
        BankType.LANDING_PAGE,
        "Section logic, claims, proof, friction, and embedded videos",
        "experience",
    ),
    BankType.VOC: BankSpec(
        BankType.VOC,
        "Comments, reviews, objections, and desire language",
        "experience",
    ),
    BankType.RESEARCH: BankSpec(
        BankType.RESEARCH,
        "News, medical research, and competitor developments",
        "world_fact",
    ),
    BankType.REFLECTION: BankSpec(
        BankType.REFLECTION,
        "Durable lessons, shifts, emerging rules, and pattern summaries",
        "mental_model",
    ),
    BankType.SEEDS: BankSpec(
        BankType.SEEDS,
        "Ideation seeds with source metadata (swipe/organic/research/template/internal/gambit)",
        "experience",
    ),
    BankType.PRIMERS: BankSpec(
        BankType.PRIMERS,
        "Living primer docs (ad, hook, headline) per offer",
        "world_fact",
    ),
}


def bank_id_for(account_id: str, bank_type: BankType, offer_id: str | None = None) -> str:
    """Generate a deterministic bank ID.

    Examples:
        ``acct_142_core``
        ``acct_142_offer_7``
        ``acct_142_creatives``
    """
    base = f"{account_id}_{bank_type.value}"
    if offer_id and bank_type == BankType.OFFER:
        base = f"{account_id}_offer_{offer_id}"
    return base


async def provision_account_banks(
    account_id: str,
    offer_ids: list[str] | None = None,
) -> dict[str, str]:
    """Create all standard banks for an account. Idempotent.

    Returns a mapping of bank_type -> bank_id.
    """
    created: dict[str, str] = {}

    for bank_type, spec in BANK_SPECS.items():
        if bank_type == BankType.OFFER and offer_ids:
            for oid in offer_ids:
                bid = bank_id_for(account_id, bank_type, oid)
                await _ensure_bank(bid, spec)
                created[f"offer_{oid}"] = bid
        else:
            bid = bank_id_for(account_id, bank_type)
            await _ensure_bank(bid, spec)
            created[bank_type.value] = bid

    return created


async def provision_offer_bank(account_id: str, offer_id: str) -> str:
    """Create or verify the offer-specific bank."""
    spec = BANK_SPECS[BankType.OFFER]
    bid = bank_id_for(account_id, BankType.OFFER, offer_id)
    await _ensure_bank(bid, spec)
    return bid


async def _ensure_bank(bank_id: str, spec: BankSpec) -> None:
    """Create bank if it doesn't exist — swallow 409 conflicts."""
    try:
        await hindsight_client.create_bank(
            bank_id,
            description=spec.description,
            metadata={"bank_type": spec.bank_type.value},
        )
        logger.info("hindsight.bank_created id=%s", bank_id)
    except Exception:
        # Bank may already exist — log and continue
        logger.debug("hindsight.bank_exists_or_error id=%s", bank_id)


def recall_scope_for_worker(worker_name: str, account_id: str, offer_id: str | None = None) -> list[str]:
    """Return the allowed bank IDs for a given worker family.

    Enforces narrow recall scopes per the blueprint.
    """
    scope_map: dict[str, list[BankType]] = {
        # Analysis workers
        "offer_intelligence": [BankType.CORE, BankType.OFFER],
        "creative_ingest": [BankType.CREATIVE],
        "landing_page_analyzer": [BankType.LANDING_PAGE, BankType.OFFER],
        "video_transcript": [BankType.LANDING_PAGE, BankType.CREATIVE],
        "voc_miner": [BankType.VOC],
        "competitor_monitor": [BankType.CREATIVE, BankType.RESEARCH],
        "domain_research": [BankType.RESEARCH],
        "audience_psychology": [BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        "proof_inventory": [BankType.OFFER, BankType.LANDING_PAGE, BankType.RESEARCH],
        "differentiation": [BankType.OFFER, BankType.CREATIVE, BankType.RESEARCH],
        # Ideation workers
        "hook_engineer": [BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.REFLECTION],
        "brief_composer": [BankType.OFFER, BankType.CREATIVE, BankType.REFLECTION, BankType.SEEDS],
        "organic_discovery": [BankType.OFFER, BankType.SEEDS],
        "swipe_miner": [BankType.CREATIVE, BankType.SEEDS],
        "coverage_matrix": [BankType.SEEDS, BankType.CREATIVE, BankType.OFFER, BankType.REFLECTION],
        # Writing workers
        "copy_generator": [BankType.OFFER, BankType.CREATIVE, BankType.VOC, BankType.PRIMERS],
        "hook_generator": [BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.PRIMERS],
        "headline_generator": [BankType.OFFER, BankType.CREATIVE, BankType.PRIMERS],
        "copy_shape_police": [BankType.OFFER, BankType.CREATIVE],
        "compression_tax": [BankType.OFFER],
        # Creative workers
        "image_concept_generator": [BankType.CREATIVE, BankType.VOC, BankType.OFFER],
        "image_prompt_generator": [BankType.CREATIVE],
        "creative_loopback": [BankType.CREATIVE, BankType.SEEDS],
        # Iteration workers
        "iteration_planner": [BankType.OFFER, BankType.VOC, BankType.CREATIVE, BankType.LANDING_PAGE, BankType.RESEARCH, BankType.REFLECTION],
        "memory_reflection": [BankType.OFFER, BankType.CREATIVE, BankType.VOC, BankType.LANDING_PAGE, BankType.RESEARCH],
    }

    bank_types = scope_map.get(worker_name, [])
    ids: list[str] = []
    for bt in bank_types:
        if bt == BankType.OFFER and offer_id:
            ids.append(bank_id_for(account_id, bt, offer_id))
        else:
            ids.append(bank_id_for(account_id, bt))
    return ids

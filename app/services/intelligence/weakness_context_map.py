"""Maps grading weaknesses to targeted Hindsight recall queries.

When the refinement engine identifies a weakness (e.g. "weak proof anchor"),
this module maps that weakness to the best Hindsight query and bank combination
to pull targeted context for the next refinement pass.

This replaces static context across all passes with per-weakness targeted
recall — each pass gets specific examples of what "good" looks like for
the exact dimension that's failing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.hindsight.banks import BankType, bank_id_for
from app.services.hindsight.client import hindsight_client

logger = logging.getLogger(__name__)

WEAKNESS_RECALL_MAP: dict[str, list[dict[str, Any]]] = {
    "specificity": [
        {"bank": BankType.CREATIVE, "query": "specific number statistic exact quote winning hook"},
        {"bank": BankType.VOC, "query": "specific customer language exact phrase number"},
    ],
    "proof_anchor": [
        {"bank": BankType.RESEARCH, "query": "clinical study RCT evidence proof statistic"},
        {"bank": BankType.CREATIVE, "query": "winning ad with strong proof evidence study citation"},
    ],
    "mechanism_connection": [
        {"bank": BankType.OFFER, "query": "mechanism how it works product delivery method"},
        {"bank": BankType.CREATIVE, "query": "winning ad mechanism bridge product connects"},
    ],
    "anti_generic": [
        {"bank": BankType.CREATIVE, "query": "unique differentiated hook competitor cannot use"},
        {"bank": BankType.OFFER, "query": "differentiation unique proprietary ingredient feature"},
    ],
    "emotional_impact": [
        {"bank": BankType.VOC, "query": "emotional pain fear desire frustration relief customer language"},
        {"bank": BankType.CREATIVE, "query": "emotional winning ad visceral response trigger"},
    ],
    "awareness_match": [
        {"bank": BankType.CREATIVE, "query": "awareness level unaware problem solution product calibrated"},
        {"bank": BankType.VOC, "query": "customer awareness language problem solution product knowledge"},
    ],
    "hook_strength": [
        {"bank": BankType.CREATIVE, "query": "winning hook opening line scroll stop attention"},
        {"bank": BankType.VOC, "query": "surprising claim question concern audience language"},
    ],
    "mechanism_bridge": [
        {"bank": BankType.OFFER, "query": "mechanism how product delivers result path"},
        {"bank": BankType.RESEARCH, "query": "mechanism evidence study explaining how it works"},
    ],
    "proof_density": [
        {"bank": BankType.RESEARCH, "query": "proof evidence study testimonial statistic citation"},
        {"bank": BankType.CREATIVE, "query": "winning ad with multiple proof elements dense evidence"},
    ],
    "cta_earned": [
        {"bank": BankType.CREATIVE, "query": "winning ad belief transfer CTA earned natural"},
        {"bank": BankType.OFFER, "query": "offer CTA constraint risk reversal guarantee"},
    ],
    "compression": [
        {"bank": BankType.CREATIVE, "query": "tight compressed winning copy no filler every word earns"},
    ],
    "scroll_stop": [
        {"bank": BankType.CREATIVE, "query": "scroll stop thumb stop winning image visual attention"},
    ],
    "native_feed": [
        {"bank": BankType.CREATIVE, "query": "native organic feed look not polished ad"},
    ],
    "emotional_trigger": [
        {"bank": BankType.CREATIVE, "query": "emotional trigger curiosity discomfort WTF visceral"},
    ],
    "uniqueness": [
        {"bank": BankType.CREATIVE, "query": "unique concept different from category typical ads"},
    ],
    "concept_diversity": [
        {"bank": BankType.CREATIVE, "query": "diverse concept sources SCRAWLS reptile wild audience"},
    ],
}


async def get_weakness_context(
    weakness_name: str,
    account_id: str,
    offer_id: str | None = None,
    top_k: int = 5,
) -> str:
    """Pull targeted Hindsight context for a specific weakness dimension.

    Returns formatted text suitable for injecting into a refinement prompt.
    """
    recall_specs = WEAKNESS_RECALL_MAP.get(weakness_name, [])
    if not recall_specs:
        return ""

    results: list[str] = []

    for spec in recall_specs:
        bank_type: BankType = spec["bank"]
        query: str = spec["query"]
        bid = bank_id_for(account_id, bank_type, offer_id)

        try:
            memories = await hindsight_client.recall(
                bank_id=bid,
                query=query,
                top_k=top_k,
            )
            for m in memories:
                content = m.get("content", "")
                if content:
                    results.append(
                        f"[{bank_type.value}] {content[:500]}"
                    )
        except Exception as exc:
            logger.debug(
                "weakness_context.recall_failed weakness=%s bank=%s error=%s",
                weakness_name, bank_type.value, exc,
            )

    if not results:
        return ""

    return (
        f"\n\nTARGETED CONTEXT FOR IMPROVING '{weakness_name}':\n"
        + "\n".join(results[:10])
    )


async def get_top_weakness_context(
    weaknesses: list[str],
    account_id: str,
    offer_id: str | None = None,
    max_weaknesses: int = 3,
    top_k_per: int = 3,
) -> str:
    """Pull targeted context for the top N weaknesses from a grading pass."""
    # Focus on the most important weakness dimensions
    targeted_weaknesses = []
    for w in weaknesses:
        w_lower = w.lower()
        for key in WEAKNESS_RECALL_MAP:
            if key in w_lower:
                targeted_weaknesses.append(key)
                break

    targeted_weaknesses = targeted_weaknesses[:max_weaknesses]
    if not targeted_weaknesses:
        return ""

    all_context: list[str] = []
    for weakness_key in targeted_weaknesses:
        ctx = await get_weakness_context(
            weakness_key, account_id, offer_id, top_k=top_k_per,
        )
        if ctx:
            all_context.append(ctx)

    return "\n".join(all_context)

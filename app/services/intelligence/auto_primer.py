"""Auto-primer update system — winners automatically update primers.

When performance data identifies winners, the system:
1. Analyzes what made the winner effective
2. Compares against the current primer
3. Suggests or automatically adds the winner to the primer
4. Removes underperformers that no longer earn their place

The primer is a LIVING document. It evolves every cycle.
Winners from this cycle become next cycle's primer material.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.knowledge.primers import PrimerType, primer_store
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker
from app.services.llm.router import Capability, router

logger = logging.getLogger(__name__)

PRIMER_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "updated_primer": {"type": "string"},
        "additions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "removals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content_snippet": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "unchanged_count": {"type": "integer"},
    },
}


async def update_primer_from_winners(
    account_id: str,
    offer_id: str,
    primer_type: PrimerType,
    winners: list[dict[str, Any]],
    losers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Update a primer based on new winner/loser data.

    Args:
        account_id: Which business
        offer_id: Which offer
        primer_type: ad_primer, hook_primer, or headline_primer
        winners: List of winning creative elements with performance data
        losers: Optional list of underperformers to consider removing

    Returns:
        Update result with additions, removals, and the new primer content
    """
    # Get current primer
    current_primer = await primer_store.get(account_id, offer_id, primer_type)
    if not current_primer:
        current_primer = "No existing primer — this will be the first version."

    winners_text = json.dumps(winners, indent=1, default=str)[:4000]
    losers_text = json.dumps(losers or [], indent=1, default=str)[:2000]

    result = await router.generate(
        capability=Capability.REFLECTION,
        system_prompt=(
            f"You are a Primer Curator for {primer_type.value}.\n\n"
            "Rules:\n"
            "- A primer should contain 10-12 of the BEST examples\n"
            "- Winners with strong performance should be ADDED\n"
            "- Underperformers that no longer earn their place should be REMOVED\n"
            "- Each example separated by ###\n"
            "- Maintain diversity: mix of awareness levels, angles, and styles\n"
            "- The primer should represent the CURRENT best, not historical best\n"
            "- If adding a winner that's similar to an existing entry, replace the weaker one\n"
            "- Return the FULL updated primer content, not just changes"
        ),
        user_prompt=(
            f"Update this primer based on new performance data.\n\n"
            f"CURRENT PRIMER:\n{current_primer}\n\n"
            f"NEW WINNERS (add these if they earn a spot):\n{winners_text}\n\n"
            f"UNDERPERFORMERS (consider removing):\n{losers_text}\n\n"
            f"Return the updated primer with 10-12 entries, separated by ###."
        ),
        temperature=0.2,
        max_tokens=6000,
        json_schema=PRIMER_UPDATE_SCHEMA,
    )

    if result.get("_parse_error"):
        return {"success": False, "error": "Failed to parse primer update"}

    updated_content = result.get("updated_primer", "")
    if updated_content:
        await primer_store.save(account_id, offer_id, primer_type, updated_content)

    additions = result.get("additions", [])
    removals = result.get("removals", [])

    logger.info(
        "primer.auto_updated account=%s offer=%s type=%s additions=%d removals=%d",
        account_id, offer_id, primer_type.value, len(additions), len(removals),
    )

    return {
        "success": True,
        "primer_type": primer_type.value,
        "additions": additions,
        "removals": removals,
        "unchanged_count": result.get("unchanged_count", 0),
    }


async def auto_update_all_primers(
    account_id: str,
    offer_id: str,
    performance_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Automatically update all three primers based on performance data.

    Extracts winners and losers from performance data, then updates
    ad primer, hook primer, and headline primer.
    """
    # Recall recent creative from the account
    memories = await recall_for_worker(
        "iteration_planner",
        account_id,
        "winning ad hook headline creative performance best worst",
        offer_id=offer_id,
        top_k=30,
    )

    # Split into categories based on evidence type
    ad_winners: list[dict[str, Any]] = []
    hook_winners: list[dict[str, Any]] = []
    headline_winners: list[dict[str, Any]] = []

    for asset_id, metrics in performance_data.get("assets", {}).items():
        roas = metrics.get("roas", 0)
        cpa = metrics.get("cpa", 999)
        is_winner = roas > 2.0 or cpa < metrics.get("target_cpa", 50)

        if is_winner:
            content = metrics.get("content", {})
            if content.get("body"):
                ad_winners.append({"copy": content.get("body"), "performance": metrics})
            if content.get("hook"):
                hook_winners.append({"hook": content.get("hook"), "performance": metrics})
            if content.get("headline"):
                headline_winners.append({"headline": content.get("headline"), "performance": metrics})

    updates: list[dict[str, Any]] = []

    if ad_winners:
        result = await update_primer_from_winners(
            account_id, offer_id, PrimerType.AD, ad_winners,
        )
        updates.append(result)

    if hook_winners:
        result = await update_primer_from_winners(
            account_id, offer_id, PrimerType.HOOK, hook_winners,
        )
        updates.append(result)

    if headline_winners:
        result = await update_primer_from_winners(
            account_id, offer_id, PrimerType.HEADLINE, headline_winners,
        )
        updates.append(result)

    return updates

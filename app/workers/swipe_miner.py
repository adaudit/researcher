"""Swipe Miner Worker — extracts competitive intelligence from ad libraries.

Input:  Competitor brand queries + platform params
Output: Competitive swipes with strategic analysis + seeds
Banks:  recall from CREATIVE, write to CREATIVE + SEEDS
Uses:   ScrapCreators for ad library data
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.prompts.systems import SWIPE_MINER_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.services.llm.schemas import SWIPE_MINER_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class SwipeMinerWorker(BaseWorker):
    contract = SkillContract(
        skill_name="swipe_miner",
        purpose="Mine competitor ads from ad libraries for format types, spend signals, hooks, and seeds",
        accepted_input_types=["competitor_queries", "ad_library_data"],
        recall_scope=[BankType.CREATIVE, BankType.SEEDS],
        write_scope=[BankType.CREATIVE, BankType.SEEDS],
        steps=[
            "recall_creative_context",
            "fetch_competitor_ads",
            "llm_analyze_swipes",
            "extract_seeds",
            "retain_to_banks",
        ],
        quality_checks=[
            "running_duration_must_be_noted",
            "format_type_must_be_identified",
            "seeds_must_be_actionable",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall existing creative context to avoid redundancy
        memories = await recall_for_worker(
            "swipe_miner",
            account_id,
            "competitor ad creative swipe winning format hook angle",
            offer_id=offer_id,
            top_k=15,
        )

        existing_context = "\n".join(
            f"- {m.get('content', '')}" for m in memories
        ) if memories else "No existing competitive intelligence."

        # Fetch competitor ads
        raw_ads: list[dict[str, Any]] = []
        competitor_queries = params.get("competitor_queries", [])

        if competitor_queries:
            try:
                from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

                for query in competitor_queries:
                    brand = query.get("brand", "")
                    platform = query.get("platform", "meta")

                    if platform == "meta":
                        result = await scrapecreators_client.meta.search_ad_library(
                            query=brand, country="US", limit=20,
                        )
                        raw_ads.extend(result.data)
                    elif platform == "tiktok":
                        result = await scrapecreators_client.tiktok.search_ads(
                            query=brand, country="US", limit=20,
                        )
                        raw_ads.extend(result.data)

            except Exception as exc:
                return WorkerOutput(
                    worker_name=self.contract.skill_name,
                    success=False,
                    errors=[f"Failed to fetch competitor ads: {exc}"],
                )

        # Include pre-fetched ad data
        pre_fetched = params.get("ad_library_data", [])
        if pre_fetched:
            raw_ads.extend(pre_fetched)

        if not raw_ads:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No ads to analyze — provide competitor_queries or ad_library_data"],
            )

        ads_text = json.dumps(raw_ads[:25], indent=1, default=str)[:12000]

        training_context = get_training_context()
        result = await router.generate(
            capability=Capability.STRATEGIC_REASONING,
            system_prompt=f"{SWIPE_MINER_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Analyze these competitor ads and extract strategic intelligence.\n\n"
                f"EXISTING COMPETITIVE INTEL:\n{existing_context}\n\n"
                f"COMPETITOR ADS ({len(raw_ads)} items):\n{ads_text}\n\n"
                f"For each ad: identify format, running duration, spend signal, hook, angle, "
                f"and proof elements. Extract actionable seeds. Map competitive themes."
            ),
            temperature=0.3,
            max_tokens=8000,
            json_schema=SWIPE_MINER_SCHEMA,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Retain swipes to CREATIVE bank
        observations: list[dict[str, Any]] = []
        for swipe in result.get("swipes", []):
            swipe_content = (
                f"Competitor swipe ({swipe.get('advertiser', 'unknown')}): "
                f"Format: {swipe.get('format_type', '')}. "
                f"Running: {swipe.get('running_duration', '')}. "
                f"Hook: {swipe.get('hook_analysis', '')}. "
                f"Angle: {swipe.get('angle_analysis', '')}."
            )
            await retain_observation(
                account_id=account_id,
                bank_type=BankType.CREATIVE,
                content=swipe_content,
                offer_id=offer_id,
                source_type="competitive",
                evidence_type="competitive_swipe",
                confidence_score=0.7,
            )

        # Retain seeds to SEEDS bank
        for swipe in result.get("swipes", []):
            if swipe.get("seed_potential") in ("high", "medium"):
                seed_content = (
                    f"Seed (swipe): Derived from {swipe.get('advertiser', 'competitor')} ad. "
                    f"Format: {swipe.get('format_type', '')}. "
                    f"Angle: {swipe.get('angle_analysis', '')}."
                )
                mem_result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.SEEDS,
                    content=seed_content,
                    offer_id=offer_id,
                    source_type="swipe",
                    evidence_type="ideation_seed",
                    confidence_score=0.6,
                    extra_metadata={"seed_source": "swipe"},
                )
                if mem_result:
                    observations.append({"type": "seed", "memory_ref": mem_result.get("id")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "swipe_analysis": result,
                "swipe_count": len(result.get("swipes", [])),
                "ads_analyzed": len(raw_ads),
            },
            observations=observations,
        )

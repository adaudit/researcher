"""Organic Discovery Worker — finds trending content to mine for seeds.

Input:  Offer context + platform search params
Output: Seeds extracted from viral organic content
Banks:  recall from OFFER, write to SEEDS
Uses:   ScrapCreators for platform content
"""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.base_training import get_training_context
from app.prompts.systems import ORGANIC_DISCOVERY_SYSTEM
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.services.llm.schemas import ORGANIC_DISCOVERY_SCHEMA
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput


class OrganicDiscoveryWorker(BaseWorker):
    contract = SkillContract(
        skill_name="organic_discovery",
        purpose="Discover trending organic content and extract hooks, formats, and angles as seeds",
        accepted_input_types=["platform_searches", "niche_keywords"],
        recall_scope=[BankType.OFFER, BankType.SEEDS],
        write_scope=[BankType.SEEDS],
        steps=[
            "recall_offer_context",
            "fetch_organic_content",
            "llm_extract_seeds",
            "retain_seeds_to_bank",
        ],
        quality_checks=[
            "seeds_must_be_specific_enough_for_briefs",
            "relevance_to_offer_must_be_assessed",
            "source_attribution_required",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        # Recall offer context for relevance filtering
        memories = await recall_for_worker(
            "organic_discovery",
            account_id,
            "offer mechanism audience target niche product category",
            offer_id=offer_id,
            top_k=10,
        )

        offer_context = "\n".join(
            f"- {m.get('content', '')}" for m in memories
        ) if memories else "No offer context available."

        # Fetch organic content from platforms
        raw_content: list[dict[str, Any]] = []
        platform_searches = params.get("platform_searches", [])
        niche_keywords = params.get("niche_keywords", [])

        if platform_searches or niche_keywords:
            try:
                from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

                for search in platform_searches:
                    platform = search.get("platform", "tiktok")
                    query = search.get("query", "")
                    if not query:
                        continue

                    if platform == "tiktok":
                        result = await scrapecreators_client.tiktok.search_videos(query=query, count=20)
                        raw_content.extend(result.data)
                    elif platform == "youtube":
                        result = await scrapecreators_client.youtube.search(query=query, count=20)
                        raw_content.extend(result.data)
                    elif platform == "instagram":
                        result = await scrapecreators_client.instagram.search_hashtag(hashtag=query, count=20)
                        raw_content.extend(result.data)

            except Exception as exc:
                return WorkerOutput(
                    worker_name=self.contract.skill_name,
                    success=False,
                    errors=[f"Failed to fetch organic content: {exc}"],
                )

        # If no fetched content, use any pre-provided content
        pre_fetched = params.get("content_items", [])
        if pre_fetched:
            raw_content.extend(pre_fetched)

        if not raw_content:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["No content to analyze — provide platform_searches or content_items"],
            )

        content_text = json.dumps(raw_content[:30], indent=1, default=str)[:10000]

        training_context = get_training_context()
        result = await router.generate(
            capability=Capability.TEXT_EXTRACTION,
            system_prompt=f"{ORGANIC_DISCOVERY_SYSTEM}\n\n{training_context}",
            user_prompt=(
                f"Analyze this organic content and extract seeds for creative ideation.\n\n"
                f"OFFER CONTEXT (filter for relevance):\n{offer_context}\n\n"
                f"ORGANIC CONTENT ({len(raw_content)} items):\n{content_text}\n\n"
                f"Extract hooks, formats, angles. Each seed must be specific enough "
                f"to develop into an ad brief."
            ),
            temperature=0.4,
            max_tokens=6000,
            json_schema=ORGANIC_DISCOVERY_SCHEMA,
        )

        if result.get("_parse_error"):
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=False,
                errors=["Failed to parse LLM response"],
            )

        # Retain seeds to SEEDS bank
        observations: list[dict[str, Any]] = []
        for seed in result.get("seeds", []):
            seed_content = (
                f"Seed ({seed.get('source_type', 'organic')}): {seed.get('seed_text', '')}. "
                f"Hook: {seed.get('hook_extracted', '')}. "
                f"Format: {seed.get('format_type', '')}. "
                f"Angle: {seed.get('angle_extracted', '')}. "
                f"Potential: {seed.get('potential', 'unknown')}."
            )
            mem_result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.SEEDS,
                content=seed_content,
                offer_id=offer_id,
                source_type="organic",
                evidence_type="ideation_seed",
                confidence_score=0.6,
                extra_metadata={
                    "seed_source": seed.get("source_type", "organic"),
                    "platform": seed.get("source_platform", "unknown"),
                },
            )
            if mem_result:
                observations.append({"type": "seed", "memory_ref": mem_result.get("id")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "organic_seeds": result,
                "seed_count": len(result.get("seeds", [])),
                "content_analyzed": len(raw_content),
            },
            observations=observations,
        )

"""Creative Ingest Worker — LLM-powered creative analysis and ingestion.

Input:  Winning ads, uploads, exports, links, OR platform search queries
Output: Normalized creative observations with strategic analysis
Banks:  retain to creative bank
Guard:  Must preserve source linkage

Uses LLM intelligence to understand WHY creatives work — not just
what the headline says, but what hook type it uses, what angle it
takes, what proof elements are present, and what structure drives it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.extraction_frameworks import get_framework_prompt
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

CREATIVE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "creatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_url": {"type": "string"},
                    "hook_text": {"type": "string"},
                    "hook_type": {"type": "string"},
                    "angle": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "format_structure": {"type": "string"},
                    "proof_elements": {"type": "array", "items": {"type": "string"}},
                    "mechanism_reference": {"type": "string"},
                    "why_it_works": {"type": "string"},
                    "anti_generic_assessment": {"type": "string"},
                },
            },
        },
    },
}


class CreativeIngestWorker(BaseWorker):
    contract = SkillContract(
        skill_name="creative_ingest",
        purpose="Ingest winning creatives and extract strategic observations with LLM analysis",
        accepted_input_types=[
            "ad_export", "creative_link", "screenshot", "upload",
            "meta_ad_library_search", "tiktok_ad_search", "platform_url",
        ],
        recall_scope=[BankType.CREATIVE],
        write_scope=[BankType.CREATIVE],
        steps=[
            "fetch_from_platform_if_needed",
            "llm_analyze_creatives",
            "extract_hook_angle_structure",
            "identify_proof_elements",
            "assess_anti_generic",
            "retain_observations",
        ],
        quality_checks=[
            "every_observation_must_link_to_source",
            "hook_extraction_must_preserve_exact_text",
            "why_it_works_analysis_required",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        creatives = params.get("creatives", [])

        # ── Live acquisition: fetch from platforms if search queries provided ──
        platform_searches = params.get("platform_searches", [])
        if platform_searches:
            fetched = await self._fetch_from_platforms(platform_searches)
            creatives.extend(fetched)

        # ── Process ad library URLs ──
        ad_library_urls = params.get("ad_library_urls", [])
        if ad_library_urls:
            fetched = await self._fetch_ad_library_urls(ad_library_urls)
            creatives.extend(fetched)

        if not creatives:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=True,
                data={"ingested_count": 0},
                observations=[],
            )

        # ── LLM analysis: understand WHY each creative works ──
        creatives_text = json.dumps(creatives[:20], indent=1, default=str)[:8000]
        training_context = get_training_context(include_examples=False)
        framework_prompt = get_framework_prompt("ad_creative")

        analysis = await router.generate(
            capability=Capability.TEXT_EXTRACTION,
            system_prompt=(
                "You are a Creative Intelligence Analyst. For each creative, extract:\n"
                "- The exact hook text and its type (curiosity, pain, contrarian, story, proof)\n"
                "- The strategic angle (what lens is the product seen through)\n"
                "- The awareness level it targets\n"
                "- The format/structure (UGC, talking head, text overlay, carousel, etc.)\n"
                "- Any proof elements present\n"
                "- Whether it references a mechanism\n"
                "- WHY it works (or doesn't) — the strategic insight, not just description\n"
                "- Anti-generic assessment: could a competitor use this unchanged?\n\n"
                f"{framework_prompt}\n\n{training_context}"
            ),
            user_prompt=f"Analyze these {len(creatives)} creatives:\n\n{creatives_text}",
            temperature=0.2,
            max_tokens=6000,
            json_schema=CREATIVE_ANALYSIS_SCHEMA,
        )

        # Retain analyzed observations
        for item in analysis.get("creatives", []):
            hook_text = item.get("hook_text", "")
            why_it_works = item.get("why_it_works", "")
            source_url = item.get("source_url", "")

            content = (
                f"Creative: Hook ({item.get('hook_type', 'unknown')}): {hook_text}. "
                f"Angle: {item.get('angle', 'unknown')}. "
                f"Awareness: {item.get('awareness_level', 'unknown')}. "
                f"Format: {item.get('format_structure', 'unknown')}. "
                f"Why it works: {why_it_works}. "
                f"Anti-generic: {item.get('anti_generic_assessment', 'not assessed')}."
            )

            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.CREATIVE,
                content=content,
                offer_id=offer_id,
                source_type="platform_fetch" if platform_searches else "upload",
                source_url=source_url,
                evidence_type="creative_analysis",
                confidence_score=0.8,
            )
            if result:
                observations.append({
                    "type": "creative_analysis",
                    "hook_type": item.get("hook_type"),
                    "source": source_url,
                    "memory_ref": result.get("id"),
                })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "ingested_count": len(creatives),
                "analyzed_count": len(analysis.get("creatives", [])),
                "fetched_from_platforms": len(platform_searches),
                "_llm_trace": {
                    "capability": "text_extraction",
                    "provider": "anthropic",
                    "model": "auto",
                    "system_prompt": "creative_analysis",
                    "user_prompt": f"analyze {len(creatives)} creatives",
                    "response": json.dumps(analysis)[:1000],
                    "quality_score": 1 if not analysis.get("_parse_error") else 0,
                },
            },
            observations=observations,
        )

    async def _fetch_from_platforms(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch ads from ScrapCreators based on search queries."""
        from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

        creatives: list[dict[str, Any]] = []

        for search in searches:
            platform = search.get("platform", "meta")
            query = search.get("query", "")
            limit = search.get("limit", 20)
            country = search.get("country", "US")

            if not query:
                continue

            try:
                if platform == "meta":
                    response = await scrapecreators_client.meta.search_ad_library(
                        query, country=country, limit=limit
                    )
                elif platform == "tiktok":
                    response = await scrapecreators_client.tiktok.search_ads(
                        query, country=country, limit=limit
                    )
                else:
                    logger.warning("creative_ingest: unsupported platform %s", platform)
                    continue

                for item in response.data:
                    creatives.append({
                        "type": "ad",
                        "headline": item.get("title") or item.get("headline") or item.get("ad_creative_link_title", ""),
                        "body_text": item.get("body") or item.get("description") or item.get("ad_text", ""),
                        "source_url": item.get("url") or item.get("snapshot_url") or item.get("ad_url", ""),
                        "platform": platform,
                    })

            except Exception as exc:
                logger.warning(
                    "creative_ingest.platform_fetch_failed platform=%s query=%s error=%s",
                    platform, query, exc,
                )

        return creatives

    async def _fetch_ad_library_urls(
        self, urls: list[str]
    ) -> list[dict[str, Any]]:
        """Scrape individual ad library URLs using Scrapling."""
        from app.services.acquisition.connectors.web_scraper import web_scraper

        creatives: list[dict[str, Any]] = []

        for url in urls:
            try:
                result = await web_scraper.crawl_url(url, stealth=True)
                if result.text_content:
                    creatives.append({
                        "type": "ad",
                        "headline": result.title or "",
                        "body_text": result.text_content[:2000],
                        "source_url": url,
                        "platform": "meta_ad_library",
                    })
            except Exception as exc:
                logger.warning("creative_ingest.url_fetch_failed url=%s error=%s", url, exc)

        return creatives

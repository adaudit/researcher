"""Creative Ingest Worker

Input:  Winning ads, uploads, exports, links, OR platform search queries
Output: Normalized creative observations
Banks:  retain to creative bank
Guard:  Must preserve source linkage

Now with live acquisition: when given platform URLs or search queries,
uses ScrapCreators to fetch real ad data and feed it through extractors.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


class CreativeIngestWorker(BaseWorker):
    contract = SkillContract(
        skill_name="creative_ingest",
        purpose="Ingest winning creatives and extract structured observations",
        accepted_input_types=[
            "ad_export", "creative_link", "screenshot", "upload",
            "meta_ad_library_search", "tiktok_ad_search", "platform_url",
        ],
        recall_scope=[BankType.CREATIVE],
        write_scope=[BankType.CREATIVE],
        steps=[
            "fetch_from_platform_if_needed",
            "classify_creative_type",
            "extract_hook",
            "extract_angle",
            "extract_structure",
            "identify_proof_elements",
            "retain_observations",
        ],
        quality_checks=[
            "every_observation_must_link_to_source",
            "hook_extraction_must_preserve_exact_text",
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

        for creative in creatives:
            source_url = creative.get("source_url", "")
            artifact_id = creative.get("artifact_id")
            creative_type = creative.get("type", "unknown")
            headline = creative.get("headline", "")
            body_text = creative.get("body_text", "")

            if headline:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CREATIVE,
                    content=f"Winning creative hook ({creative_type}): {headline}",
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="upload" if not platform_searches else "platform_fetch",
                    source_url=source_url,
                    evidence_type="hook_pattern",
                    confidence_score=0.8,
                )
                if result:
                    observations.append({
                        "type": "hook_pattern",
                        "source": source_url,
                        "memory_ref": result.get("id"),
                    })

            if body_text:
                await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CREATIVE,
                    content=f"Creative body structure ({creative_type}): {body_text[:500]}",
                    offer_id=offer_id,
                    artifact_id=artifact_id,
                    source_type="upload" if not platform_searches else "platform_fetch",
                    source_url=source_url,
                    evidence_type="creative_structure",
                    confidence_score=0.7,
                )

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "ingested_count": len(creatives),
                "fetched_from_platforms": len(platform_searches),
            },
            observations=observations,
        )

    async def _fetch_from_platforms(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch ads from ScrapCreators based on search queries.

        Each search: {"platform": "meta"|"tiktok", "query": "...", "limit": 20}
        """
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
        """Scrape individual Meta Ad Library URLs using Scrapling."""
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

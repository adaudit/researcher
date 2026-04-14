"""Competitor Monitor Worker

Input:  Competitor names/URLs, ad search queries, OR page URLs to monitor
Output: Competitor themes, style changes, market positioning signals
Banks:  retain to creative and research banks
Guard:  Must label freshness and source coverage

Now with live acquisition: uses ScrapCreators for ad library search
and Scrapling for competitor page change detection.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


class CompetitorMonitorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="competitor_monitor",
        purpose="Track competitor creative themes, style shifts, and market positioning",
        accepted_input_types=[
            "ad_reference", "page_snapshot", "swipe_file",
            "competitor_search", "page_monitor",
        ],
        recall_scope=[BankType.CREATIVE, BankType.RESEARCH],
        write_scope=[BankType.CREATIVE, BankType.RESEARCH],
        steps=[
            "fetch_competitor_ads_if_needed",
            "monitor_competitor_pages_if_needed",
            "classify_competitor_assets",
            "extract_themes_and_angles",
            "detect_style_changes",
            "compare_with_prior_observations",
            "retain_competitive_signals",
        ],
        quality_checks=[
            "freshness_must_be_labeled",
            "source_coverage_must_be_stated",
            "competitor_identity_must_be_clear",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        competitors = params.get("competitors", [])

        # ── Live acquisition: search ad libraries for competitor ads ──
        competitor_searches = params.get("competitor_searches", [])
        if competitor_searches:
            fetched = await self._search_competitor_ads(competitor_searches)
            competitors.extend(fetched)

        # ── Live acquisition: monitor competitor pages for changes ──
        page_monitors = params.get("page_monitors", [])
        page_changes: list[dict[str, Any]] = []
        if page_monitors:
            page_changes = await self._monitor_pages(page_monitors)

        # ── Process competitor assets (manual + fetched) ──
        for comp in competitors:
            name = comp.get("name", "unknown")
            assets = comp.get("assets", [])

            for asset in assets:
                theme = asset.get("theme", "")
                angle = asset.get("angle", "")
                source_url = asset.get("source_url", "")
                body_text = asset.get("body_text", "")

                content_parts = []
                if theme:
                    content_parts.append(f"Theme: {theme}")
                if angle:
                    content_parts.append(f"Angle: {angle}")
                if body_text:
                    content_parts.append(f"Copy: {body_text[:300]}")

                if content_parts:
                    content = f"Competitor ({name}): {'. '.join(content_parts)}"
                    result = await retain_observation(
                        account_id=account_id,
                        bank_type=BankType.CREATIVE,
                        content=content,
                        offer_id=offer_id,
                        source_type="platform_fetch" if competitor_searches else "manual",
                        source_url=source_url,
                        evidence_type="competitive_signal",
                        confidence_score=0.7,
                        extra_metadata={"competitor": name},
                    )
                    if result:
                        observations.append({
                            "type": "competitive_theme",
                            "competitor": name,
                            "memory_ref": result.get("id"),
                        })

        # ── Retain page change observations ──
        for change in page_changes:
            if change.get("changed"):
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.RESEARCH,
                    content=f"Competitor page changed: {change['url']}. {change.get('summary', '')}",
                    offer_id=offer_id,
                    source_type="page_monitor",
                    source_url=change["url"],
                    evidence_type="competitive_signal",
                    confidence_score=0.6,
                    extra_metadata={"current_hash": change.get("current_hash")},
                )
                if result:
                    observations.append({
                        "type": "page_change",
                        "url": change["url"],
                        "memory_ref": result.get("id"),
                    })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "competitors_analyzed": len(competitors),
                "pages_monitored": len(page_monitors),
                "pages_changed": len([c for c in page_changes if c.get("changed")]),
            },
            observations=observations,
        )

    async def _search_competitor_ads(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Search ad libraries for competitor ads via ScrapCreators.

        Each search: {"name": "CompetitorBrand", "query": "brand name", "platform": "meta", "limit": 20}
        """
        from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

        competitors: list[dict[str, Any]] = []

        for search in searches:
            name = search.get("name", search.get("query", "unknown"))
            query = search.get("query", name)
            platform = search.get("platform", "meta")
            limit = search.get("limit", 20)
            country = search.get("country", "US")

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
                    logger.warning("competitor_monitor: unsupported platform %s", platform)
                    continue

                assets = []
                for item in response.data:
                    assets.append({
                        "theme": item.get("title") or item.get("headline", ""),
                        "angle": "",
                        "body_text": item.get("body") or item.get("description") or item.get("ad_text", ""),
                        "source_url": item.get("url") or item.get("snapshot_url", ""),
                    })

                if assets:
                    competitors.append({"name": name, "assets": assets})

            except Exception as exc:
                logger.warning(
                    "competitor_monitor.search_failed name=%s error=%s", name, exc
                )

        return competitors

    async def _monitor_pages(
        self, monitors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Monitor competitor pages for changes via Scrapling.

        Each monitor: {"url": "https://competitor.com", "previous_hash": "abc123"}
        """
        from app.services.acquisition.connectors.web_scraper import web_scraper

        results: list[dict[str, Any]] = []

        for monitor in monitors:
            url = monitor.get("url", "")
            previous_hash = monitor.get("previous_hash")

            if not url:
                continue

            try:
                change = await web_scraper.monitor_competitor_page(url, previous_hash)
                results.append({
                    "url": url,
                    "changed": change.changed,
                    "current_hash": change.current_hash,
                    "summary": change.changes_summary or "",
                })
            except Exception as exc:
                logger.warning("competitor_monitor.page_monitor_failed url=%s error=%s", url, exc)

        return results

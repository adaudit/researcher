"""Competitor Monitor Worker — LLM-powered competitive intelligence.

Input:  Competitor names/URLs, ad search queries, OR page URLs to monitor
Output: Competitive themes, style shifts, emerging sameness, gaps
Banks:  retain to creative and research banks
Guard:  Must label freshness and source coverage

Uses LLM intelligence to analyze competitive THEMES, identify style
shifts, detect category sameness, and find gaps competitors leave open.
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

COMPETITIVE_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "competitors_using": {"type": "array", "items": {"type": "string"}},
                    "saturation_level": {"type": "string"},
                    "our_opportunity": {"type": "string"},
                },
            },
        },
        "style_shifts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shift": {"type": "string"},
                    "from_style": {"type": "string"},
                    "to_style": {"type": "string"},
                    "competitors": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "category_sameness": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "how_common": {"type": "string"},
                },
            },
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap": {"type": "string"},
                    "severity": {"type": "string"},
                    "opportunity": {"type": "string"},
                },
            },
        },
    },
}


class CompetitorMonitorWorker(BaseWorker):
    contract = SkillContract(
        skill_name="competitor_monitor",
        purpose="Track competitor creative themes, style shifts, and market positioning with LLM analysis",
        accepted_input_types=[
            "ad_reference", "page_snapshot", "swipe_file",
            "competitor_search", "page_monitor",
        ],
        recall_scope=[BankType.CREATIVE, BankType.RESEARCH],
        write_scope=[BankType.CREATIVE, BankType.RESEARCH],
        steps=[
            "fetch_competitor_ads_if_needed",
            "monitor_competitor_pages_if_needed",
            "llm_analyze_competitive_themes",
            "detect_style_shifts",
            "identify_category_sameness",
            "find_gaps_and_opportunities",
            "retain_competitive_signals",
        ],
        quality_checks=[
            "freshness_must_be_labeled",
            "source_coverage_must_be_stated",
            "competitor_identity_must_be_clear",
            "gaps_must_be_actionable",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []

        competitors = params.get("competitors", [])

        # ── Live acquisition: search ad libraries ──
        competitor_searches = params.get("competitor_searches", [])
        if competitor_searches:
            fetched = await self._search_competitor_ads(competitor_searches)
            competitors.extend(fetched)

        # ── Live acquisition: monitor pages ──
        page_monitors = params.get("page_monitors", [])
        page_changes: list[dict[str, Any]] = []
        if page_monitors:
            page_changes = await self._monitor_pages(page_monitors)

        # ── LLM analysis of competitive landscape ──
        analysis = {}
        if competitors:
            comp_text = json.dumps(competitors[:15], indent=1, default=str)[:10000]
            training_context = get_training_context(include_examples=False)
            framework_prompt = get_framework_prompt("competitor")

            analysis = await router.generate(
                capability=Capability.STRATEGIC_REASONING,
                system_prompt=(
                    "You are a Competitive Intelligence Analyst. Analyze competitor ads "
                    "and content to identify:\n"
                    "1. Recurring THEMES across competitors (what everyone is saying)\n"
                    "2. STYLE SHIFTS (how competitor creative is changing)\n"
                    "3. CATEGORY SAMENESS (where everyone sounds the same)\n"
                    "4. GAPS (what nobody is doing that represents an opportunity)\n\n"
                    f"{framework_prompt}\n\n{training_context}"
                ),
                user_prompt=(
                    f"Analyze competitive landscape from {len(competitors)} competitor data sets:\n\n"
                    f"{comp_text}"
                ),
                temperature=0.3,
                max_tokens=6000,
                json_schema=COMPETITIVE_ANALYSIS_SCHEMA,
            )

            # Retain analyzed themes
            for theme in analysis.get("themes", []):
                content = (
                    f"Competitive theme: {theme.get('theme', '')}. "
                    f"Used by: {', '.join(theme.get('competitors_using', []))}. "
                    f"Saturation: {theme.get('saturation_level', 'unknown')}. "
                    f"Opportunity: {theme.get('our_opportunity', '')}."
                )
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CREATIVE,
                    content=content,
                    offer_id=offer_id,
                    source_type="competitive_analysis",
                    evidence_type="competitive_signal",
                    confidence_score=0.7,
                )
                if result:
                    observations.append({"type": "competitive_theme", "memory_ref": result.get("id")})

            # Retain gaps as high-value insights
            for gap in analysis.get("gaps", []):
                content = (
                    f"Competitive gap: {gap.get('gap', '')}. "
                    f"Severity: {gap.get('severity', 'unknown')}. "
                    f"Opportunity: {gap.get('opportunity', '')}."
                )
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.RESEARCH,
                    content=content,
                    offer_id=offer_id,
                    source_type="competitive_analysis",
                    evidence_type="competitive_gap",
                    confidence_score=0.75,
                )
                if result:
                    observations.append({"type": "competitive_gap", "memory_ref": result.get("id")})

        # ── Retain page changes ──
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
                    observations.append({"type": "page_change", "url": change["url"], "memory_ref": result.get("id")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "competitive_analysis": analysis,
                "competitors_analyzed": len(competitors),
                "pages_monitored": len(page_monitors),
                "pages_changed": len([c for c in page_changes if c.get("changed")]),
                "themes_found": len(analysis.get("themes", [])),
                "gaps_found": len(analysis.get("gaps", [])),
            },
            observations=observations,
        )

    async def _search_competitor_ads(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Search ad libraries for competitor ads via ScrapCreators."""
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
                logger.warning("competitor_monitor.search_failed name=%s error=%s", name, exc)

        return competitors

    async def _monitor_pages(
        self, monitors: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Monitor competitor pages for changes via Scrapling."""
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

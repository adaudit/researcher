"""Cultural Pulse Worker — weekly scan of trends, concerns, and media effects.

Scans:
  - Google News RSS (niche + adjacent topics)
  - Google Trends (rising queries in the offer's category)
  - Reddit rising threads (audience subreddits)
  - ScrapCreators Twitter/X (trending conversations)
  - FDA/FTC (regulatory actions affecting the niche)

Output: Cultural state report retained to CULTURE bank.
Runs weekly before the full cycle so ideation has fresh cultural context.

Banks: recall CULTURE, OFFER, VOC | write CULTURE
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import recall_for_worker, retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trending_concerns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concern": {"type": "string"},
                    "relevance": {"type": "string"},
                    "source": {"type": "string"},
                    "hook_potential": {"type": "string"},
                },
            },
        },
        "cultural_moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "moment": {"type": "string"},
                    "timing_window": {"type": "string"},
                    "angle_opportunity": {"type": "string"},
                },
            },
        },
        "regulatory_alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "alert": {"type": "string"},
                    "severity": {"type": "string"},
                    "action_needed": {"type": "string"},
                },
            },
        },
        "rising_search_terms": {
            "type": "array",
            "items": {"type": "string"},
        },
        "weekly_summary": {"type": "string"},
    },
}


class CulturalPulseWorker(BaseWorker):
    contract = SkillContract(
        skill_name="cultural_pulse",
        purpose="Weekly scan of cultural trends, concerns, media effects, and regulatory news for the offer's niche",
        accepted_input_types=["niche_keywords", "subreddits", "competitor_names"],
        recall_scope=[BankType.CULTURE, BankType.OFFER, BankType.VOC],
        write_scope=[BankType.CULTURE],
        steps=[
            "recall_offer_context",
            "scan_news_rss",
            "scan_google_trends",
            "scan_reddit_rising",
            "scan_regulatory",
            "synthesize_cultural_state",
            "retain_to_culture_bank",
        ],
        quality_checks=[
            "every_signal_must_cite_source",
            "regulatory_alerts_must_be_flagged",
            "relevance_to_offer_must_be_assessed",
        ],
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params

        keywords = params.get("niche_keywords", [])
        subreddits = params.get("subreddits", [])

        # Recall offer context to focus the scan
        memories = await recall_for_worker(
            "cultural_pulse", account_id,
            "offer product mechanism audience niche category industry",
            offer_id=offer_id,
            top_k=10,
        )
        offer_context = "\n".join(m.get("content", "")[:200] for m in memories)

        # If no keywords provided, extract from offer context
        if not keywords and offer_context:
            keywords = await self._extract_keywords(offer_context)

        # Gather raw signals from all sources
        raw_signals: list[dict[str, Any]] = []

        for kw in keywords[:5]:
            # News
            try:
                from app.services.acquisition.connectors.news_client import news_client
                news = await news_client.search(kw, max_results=5)
                raw_signals.extend(news)
            except Exception as exc:
                logger.debug("cultural_pulse.news_failed kw=%s error=%s", kw, exc)

            # Trends
            try:
                from app.services.acquisition.connectors.trends_client import trends_client
                related = await trends_client.related_queries(kw)
                for r in related:
                    raw_signals.append({
                        "type": "rising_search",
                        "query": r.get("query", ""),
                        "value": r.get("value", 0),
                        "trend_type": r.get("type", ""),
                    })
            except Exception as exc:
                logger.debug("cultural_pulse.trends_failed kw=%s error=%s", kw, exc)

        # Reddit rising
        for sub in subreddits[:3]:
            try:
                from app.services.acquisition.connectors.reddit_client import reddit_client
                posts = await reddit_client.get_rising(sub, limit=10)
                raw_signals.extend([
                    {**p, "type": "reddit_rising", "subreddit": sub}
                    for p in posts
                ])
            except Exception as exc:
                logger.debug("cultural_pulse.reddit_failed sub=%s error=%s", sub, exc)

        # Regulatory
        for kw in keywords[:3]:
            try:
                from app.services.acquisition.connectors.regulatory_client import regulatory_client
                fda = await regulatory_client.search(kw, source="fda_api", limit=3)
                raw_signals.extend(fda)
            except Exception as exc:
                logger.debug("cultural_pulse.regulatory_failed kw=%s error=%s", kw, exc)

        if not raw_signals:
            return WorkerOutput(
                worker_name=self.contract.skill_name,
                success=True,
                data={"message": "No signals found", "keywords_scanned": keywords},
            )

        # Synthesize
        signals_text = json.dumps(raw_signals, default=str)[:10000]
        synthesis = await router.generate(
            capability=Capability.SYNTHESIS,
            system_prompt=(
                "You are a Cultural Intelligence Analyst. Synthesize raw signals "
                "into a weekly cultural state report for a creative strategy team.\n\n"
                "Focus on:\n"
                "- Trending CONCERNS the audience has this week\n"
                "- Cultural MOMENTS that could be hooked into\n"
                "- Regulatory ALERTS that affect claims/copy\n"
                "- Rising SEARCH TERMS that indicate shifting interest\n\n"
                "Rate relevance to the offer. Suggest hook angles where applicable."
            ),
            user_prompt=(
                f"OFFER CONTEXT:\n{offer_context[:2000]}\n\n"
                f"RAW SIGNALS ({len(raw_signals)} items):\n{signals_text}\n\n"
                f"Synthesize into this week's cultural state report."
            ),
            temperature=0.3,
            max_tokens=4000,
            json_schema=SYNTHESIS_SCHEMA,
        )

        # Retain synthesis to CULTURE bank
        retained = 0
        summary = synthesis.get("weekly_summary", "")
        if summary:
            try:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CULTURE,
                    content=summary,
                    offer_id=offer_id,
                    source_type="cultural_scan",
                    evidence_type="weekly_cultural_pulse",
                    confidence_score=0.7,
                )
                if result:
                    retained += 1
            except Exception as exc:
                logger.warning("cultural_pulse.retain_failed error=%s", exc)

        for concern in synthesis.get("trending_concerns", []):
            try:
                await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.CULTURE,
                    content=(
                        f"Trending concern: {concern.get('concern', '')}. "
                        f"Relevance: {concern.get('relevance', '')}. "
                        f"Hook potential: {concern.get('hook_potential', '')}"
                    ),
                    offer_id=offer_id,
                    source_type=concern.get("source", "cultural_scan"),
                    evidence_type="trending_concern",
                    confidence_score=0.6,
                )
                retained += 1
            except Exception as exc:
                logger.debug("cultural_pulse.retain_concern_failed error=%s", exc)

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "signals_scanned": len(raw_signals),
                "synthesis": synthesis,
                "retained": retained,
                "keywords_scanned": keywords,
            },
            requires_review=bool(synthesis.get("regulatory_alerts")),
        )

    async def _extract_keywords(self, offer_context: str) -> list[str]:
        """Extract niche keywords from offer context."""
        result = await router.generate(
            capability=Capability.TEXT_EXTRACTION,
            system_prompt="Extract 3-5 niche keywords for cultural monitoring from the offer context.",
            user_prompt=offer_context[:1000],
            temperature=0.1,
            max_tokens=200,
            json_schema={
                "type": "object",
                "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
            },
        )
        return result.get("keywords", [])

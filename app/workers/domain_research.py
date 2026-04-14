"""Domain Research Worker — LLM-powered research analysis.

Input:  Research queries, domain topics, PubMed queries, web search queries
Output: Domain developments, proof opportunities, scientific evidence
Banks:  retain to research bank
Guard:  Every external claim must cite source

Uses LLM intelligence (LONG_DOCUMENT for full papers, TEXT_EXTRACTION
for summaries) to extract usable statistics, mechanism evidence, and
regulatory flags — not just titles and abstracts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.knowledge.base_training import get_training_context
from app.knowledge.extraction_frameworks import get_framework_prompt
from app.services.acquisition.research import search_pubmed
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.services.llm.router import Capability, router
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)

RESEARCH_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "source": {"type": "string"},
                    "source_url": {"type": "string"},
                    "usable_statistic": {"type": "string"},
                    "mechanism_evidence": {"type": "string"},
                    "study_quality": {"type": "string"},
                    "regulatory_flags": {"type": "array", "items": {"type": "string"}},
                    "marketing_usability": {"type": "string"},
                    "proof_type": {"type": "string"},
                    "strength": {"type": "string"},
                },
            },
        },
        "proof_opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opportunity": {"type": "string"},
                    "evidence_basis": {"type": "string"},
                    "claim_it_supports": {"type": "string"},
                },
            },
        },
    },
}


class DomainResearchWorker(BaseWorker):
    contract = SkillContract(
        skill_name="domain_research",
        purpose="Research domain evidence and extract usable proof with LLM analysis",
        accepted_input_types=[
            "research_query", "domain_topic", "pubmed_query",
            "web_search_query", "forum_search",
        ],
        recall_scope=[BankType.RESEARCH],
        write_scope=[BankType.RESEARCH],
        steps=[
            "execute_research_queries",
            "execute_web_searches_if_needed",
            "execute_forum_searches_if_needed",
            "llm_analyze_findings",
            "extract_usable_statistics",
            "identify_mechanism_evidence",
            "flag_regulatory_concerns",
            "retain_research_facts",
        ],
        quality_checks=[
            "every_claim_must_cite_source",
            "publication_date_must_be_recorded",
            "findings_must_distinguish_correlation_from_causation",
            "usable_statistics_must_be_extracted",
        ],
        escalation_rule="Escalate health claims that may require regulatory review",
    )

    async def execute(self, worker_input: WorkerInput) -> WorkerOutput:
        account_id = worker_input.account_id
        offer_id = worker_input.offer_id
        params = worker_input.params
        observations: list[dict[str, Any]] = []
        requires_review = False

        queries = params.get("queries", [])
        domain = params.get("domain", "general")

        all_raw_results: list[dict[str, Any]] = []

        # ── PubMed research ──
        for query in queries:
            if domain in ("health", "medical", "supplement"):
                pubmed_results = await search_pubmed(query, max_results=5)
                for r in pubmed_results:
                    all_raw_results.append({
                        "source": "pubmed",
                        "title": r.title,
                        "summary": r.summary,
                        "url": r.url,
                        "metadata": r.metadata,
                    })
                if domain == "health":
                    requires_review = True

        # ── Forum research via Scrapling ──
        forum_searches = params.get("forum_searches", [])
        if forum_searches:
            forum_results = await self._search_forums(forum_searches)
            for fr in forum_results:
                all_raw_results.append({
                    "source": "forum",
                    "title": fr.get("title", ""),
                    "summary": fr["content"][:500],
                    "url": fr.get("url", ""),
                    "metadata": {"forum": fr["forum"], "post_count": fr.get("post_count", 0)},
                })

        # ── Reddit research via ScrapCreators ──
        reddit_searches = params.get("reddit_searches", [])
        if reddit_searches:
            reddit_results = await self._search_reddit(reddit_searches)
            for rr in reddit_results:
                all_raw_results.append({
                    "source": "reddit",
                    "title": rr["title"],
                    "summary": rr["text"][:500],
                    "url": rr.get("url", ""),
                    "metadata": {"subreddit": rr["subreddit"], "score": rr.get("score", 0)},
                })

        # ── LLM analysis of all research findings ──
        analysis = {}
        if all_raw_results:
            raw_text = json.dumps(all_raw_results[:20], indent=1, default=str)[:12000]
            training_context = get_training_context(include_examples=False)
            framework_prompt = get_framework_prompt("research")

            # Use LONG_DOCUMENT for large research batches, TEXT_EXTRACTION for smaller
            capability = (
                Capability.LONG_DOCUMENT
                if len(raw_text) > 8000
                else Capability.TEXT_EXTRACTION
            )

            analysis = await router.generate(
                capability=capability,
                system_prompt=(
                    "You are a Research Intelligence Analyst. For each research finding, extract:\n"
                    "1. USABLE STATISTICS: exact numbers that can be cited in marketing\n"
                    "2. MECHANISM EVIDENCE: how/why something works at a biological/chemical level\n"
                    "3. STUDY QUALITY: sample size, methodology, peer-review status\n"
                    "4. REGULATORY FLAGS: what can/cannot be claimed based on this evidence\n"
                    "5. MARKETING USABILITY: how strong is this for use in ad copy/landing pages\n"
                    "6. PROOF OPPORTUNITIES: what claims does this evidence support?\n\n"
                    f"{framework_prompt}\n\n{training_context}"
                ),
                user_prompt=(
                    f"Analyze these {len(all_raw_results)} research findings for "
                    f"the '{domain}' domain:\n\n{raw_text}"
                ),
                temperature=0.2,
                max_tokens=6000,
                json_schema=RESEARCH_ANALYSIS_SCHEMA,
            )

        # ── Retain analyzed findings ──
        for finding in analysis.get("findings", []):
            content = (
                f"Research: {finding.get('finding', '')}. "
                f"Source: {finding.get('source', '')}. "
                f"Usable stat: {finding.get('usable_statistic', 'none')}. "
                f"Mechanism: {finding.get('mechanism_evidence', 'none')}. "
                f"Quality: {finding.get('study_quality', 'unknown')}. "
                f"Marketing usability: {finding.get('marketing_usability', 'unknown')}."
            )
            reg_flags = finding.get("regulatory_flags", [])
            risk_level = "elevated" if reg_flags else "standard"

            result = await retain_observation(
                account_id=account_id,
                bank_type=BankType.RESEARCH,
                content=content,
                offer_id=offer_id,
                source_type="research",
                source_url=finding.get("source_url", ""),
                evidence_type="research_finding",
                confidence_score=0.8,
                domain_risk_level=risk_level,
                extra_metadata={
                    "proof_type": finding.get("proof_type", ""),
                    "strength": finding.get("strength", ""),
                    "regulatory_flags": reg_flags,
                },
            )
            if result:
                observations.append({
                    "type": "research_finding",
                    "source": finding.get("source", ""),
                    "memory_ref": result.get("id"),
                })

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "research_analysis": analysis,
                "queries_executed": len(queries),
                "forum_searches_executed": len(forum_searches),
                "reddit_searches_executed": len(reddit_searches),
                "raw_results_found": len(all_raw_results),
                "findings_analyzed": len(analysis.get("findings", [])),
                "proof_opportunities": len(analysis.get("proof_opportunities", [])),
            },
            observations=observations,
            requires_review=requires_review,
        )

    async def _search_forums(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Search forums via Scrapling."""
        from app.services.acquisition.connectors.web_scraper import web_scraper

        results: list[dict[str, Any]] = []

        for search in searches:
            base_url = search.get("url", "")
            query = search.get("query", "")

            if not base_url:
                continue

            try:
                thread_urls = await web_scraper.discover_forum_threads(
                    base_url, query=query, max_threads=10
                )
                for thread_url in thread_urls[:5]:
                    thread = await web_scraper.crawl_forum_thread(thread_url)
                    if thread.posts:
                        combined_text = "\n".join(p.content[:200] for p in thread.posts[:5])
                        results.append({
                            "forum": base_url,
                            "title": thread.title,
                            "url": thread_url,
                            "content": combined_text,
                            "post_count": len(thread.posts),
                        })
            except Exception as exc:
                logger.warning("domain_research.forum_search_failed url=%s error=%s", base_url, exc)

        return results

    async def _search_reddit(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Search Reddit via ScrapCreators."""
        from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

        results: list[dict[str, Any]] = []

        for search in searches:
            query = search.get("query", "")
            subreddit = search.get("subreddit")
            limit = search.get("limit", 10)

            if not query:
                continue

            try:
                response = await scrapecreators_client.reddit.search_posts(
                    query, subreddit=subreddit, limit=limit
                )
                for item in response.data:
                    results.append({
                        "subreddit": item.get("subreddit") or subreddit or "unknown",
                        "title": item.get("title", ""),
                        "text": item.get("selftext") or item.get("body", ""),
                        "url": item.get("permalink") or item.get("url", ""),
                        "score": item.get("score", 0),
                    })
            except Exception as exc:
                logger.warning("domain_research.reddit_search_failed query=%s error=%s", query, exc)

        return results

"""Domain Research Worker

Input:  Research queries, domain topics, PubMed queries, web search queries
Output: Domain developments, proof opportunities, scientific evidence
Banks:  retain to research bank
Guard:  Every external claim must cite source

Now with live acquisition: uses Scrapling for web-based research alongside
PubMed, and ScrapCreators for social platform research discovery.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.acquisition.research import search_pubmed
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation
from app.workers.base import BaseWorker, SkillContract, WorkerInput, WorkerOutput

logger = logging.getLogger(__name__)


class DomainResearchWorker(BaseWorker):
    contract = SkillContract(
        skill_name="domain_research",
        purpose="Monitor domain developments, scientific evidence, and proof opportunities",
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
            "filter_relevant_results",
            "extract_key_findings",
            "verify_source_citations",
            "retain_research_facts",
        ],
        quality_checks=[
            "every_claim_must_cite_source",
            "publication_date_must_be_recorded",
            "findings_must_distinguish_correlation_from_causation",
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

        all_results: list[dict[str, Any]] = []

        # ── PubMed research (existing) ──
        for query in queries:
            if domain in ("health", "medical", "supplement"):
                pubmed_results = await search_pubmed(query, max_results=5)
                for r in pubmed_results:
                    result = await retain_observation(
                        account_id=account_id,
                        bank_type=BankType.RESEARCH,
                        content=f"Research finding: {r.title}. {r.summary}",
                        offer_id=offer_id,
                        source_type="research",
                        source_url=r.url,
                        evidence_type="research_finding",
                        confidence_score=0.8,
                        domain_risk_level="elevated" if domain == "health" else "standard",
                        extra_metadata=r.metadata,
                    )
                    if result:
                        observations.append({
                            "type": "research_finding",
                            "title": r.title,
                            "url": r.url,
                            "memory_ref": result.get("id"),
                        })
                    all_results.append({"source": "pubmed", "title": r.title, "url": r.url})

                if domain == "health":
                    requires_review = True

        # ── Forum research via Scrapling ──
        forum_searches = params.get("forum_searches", [])
        if forum_searches:
            forum_results = await self._search_forums(forum_searches)
            for fr in forum_results:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.RESEARCH,
                    content=f"Forum insight ({fr['forum']}): {fr['content'][:500]}",
                    offer_id=offer_id,
                    source_type="forum",
                    source_url=fr.get("url", ""),
                    evidence_type="forum_insight",
                    confidence_score=0.5,
                )
                if result:
                    observations.append({
                        "type": "forum_insight",
                        "forum": fr["forum"],
                        "memory_ref": result.get("id"),
                    })
                all_results.append({"source": "forum", "title": fr.get("title", ""), "url": fr.get("url", "")})

        # ── Reddit research via ScrapCreators ──
        reddit_searches = params.get("reddit_searches", [])
        if reddit_searches:
            reddit_results = await self._search_reddit(reddit_searches)
            for rr in reddit_results:
                result = await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.RESEARCH,
                    content=f"Reddit research ({rr['subreddit']}): {rr['title']}. {rr['text'][:300]}",
                    offer_id=offer_id,
                    source_type="reddit",
                    source_url=rr.get("url", ""),
                    evidence_type="community_insight",
                    confidence_score=0.6,
                    extra_metadata={"subreddit": rr["subreddit"], "score": rr.get("score", 0)},
                )
                if result:
                    observations.append({
                        "type": "reddit_insight",
                        "subreddit": rr["subreddit"],
                        "memory_ref": result.get("id"),
                    })
                all_results.append({"source": "reddit", "title": rr["title"], "url": rr.get("url", "")})

        return WorkerOutput(
            worker_name=self.contract.skill_name,
            success=True,
            data={
                "queries_executed": len(queries),
                "forum_searches_executed": len(forum_searches),
                "reddit_searches_executed": len(reddit_searches),
                "results_found": len(all_results),
                "results": all_results,
            },
            observations=observations,
            requires_review=requires_review,
        )

    async def _search_forums(
        self, searches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Search forums via Scrapling.

        Each search: {"url": "https://forum.example.com", "query": "joint pain"}
        """
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
        """Search Reddit via ScrapCreators.

        Each search: {"query": "joint pain supplements", "subreddit": "Supplements", "limit": 10}
        """
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

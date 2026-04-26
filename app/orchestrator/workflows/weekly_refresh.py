"""Weekly research and reflection workflow tasks.

The weekly cycle is where the architecture earns its value:
  retain -> recall -> reflect -> publish

Jobs:
  - Top ad refresh (weekly) — ScrapCreators ad library pulls
  - Comments/reviews refresh (weekly) — ScrapCreators VOC pulls
  - Landing page diff (weekly) — Scrapling page monitoring
  - News monitor (daily) — Scrapling web search
  - Literature refresh (weekly)
  - Performance feedback ingest (daily)
  - Memory reflection (weekly)
  - Iteration synthesis (weekly)
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_top_ad_refresh")
def run_top_ad_refresh() -> dict[str, Any]:
    """Ingest current winners and notable competitor ads."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_run_top_ad_refresh_async())


async def _run_top_ad_refresh_async() -> dict[str, Any]:
    from app.workers.competitor_monitor import CompetitorMonitorWorker
    from app.workers.creative_ingest import CreativeIngestWorker

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("top_ad_refresh", "started"))

    # In production, this queries the database for all active accounts/offers
    # and runs creative ingest + competitor monitor for each
    step_log.append(build_step_log_entry("top_ad_refresh", "completed",
                                         "Placeholder — needs active account iteration"))

    return {"status": "completed", "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_voc_refresh")
def run_voc_refresh(
    account_id: str = "",
    offer_id: str = "",
    queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pull fresh comments/reviews via ScrapCreators → VOC miner."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_voc_refresh_async(account_id, offer_id, queries or [])
    )


async def _run_voc_refresh_async(
    account_id: str,
    offer_id: str,
    queries: list[dict[str, Any]],
) -> dict[str, Any]:
    step_log: list[dict] = []
    step_log.append(build_step_log_entry("voc_refresh", "started"))

    if not account_id:
        step_log.append(build_step_log_entry("voc_refresh", "skipped", "No account_id"))
        return {"status": "skipped", "step_log": step_log}

    raw_data: list[dict[str, Any]] = []

    # Fetch fresh VOC from ScrapCreators
    if queries:
        try:
            from app.services.acquisition.connectors.scrapecreators import scrapecreators_client

            for q in queries:
                platform = q.get("platform", "youtube")
                target = q.get("target", "")
                if not target:
                    continue

                if platform == "youtube":
                    result = await scrapecreators_client.youtube.get_comments(video_id=target, count=100)
                    raw_data.extend(result.data)
                elif platform == "reddit":
                    result = await scrapecreators_client.reddit.search_posts(query=target, limit=50)
                    raw_data.extend(result.data)
                elif platform == "amazon":
                    result = await scrapecreators_client.amazon.get_reviews(asin=target, count=50)
                    raw_data.extend(result.data)
                elif platform == "trustpilot":
                    result = await scrapecreators_client.trustpilot.get_reviews(business_id=target, count=50)
                    raw_data.extend(result.data)

        except Exception as exc:
            logger.error("voc_refresh.fetch_failed error=%s", exc)

    # Run through VOC miner if we have data
    if raw_data:
        from app.workers.voc_miner import VOCMinerWorker
        voc_worker = VOCMinerWorker()
        voc_result = await voc_worker.run(WorkerInput(
            account_id=account_id,
            offer_id=offer_id,
            params={"comments": raw_data},
        ))
        step_log.append(build_step_log_entry("voc_refresh", "completed",
                                             f"Processed {len(raw_data)} items"))
        return {"status": "completed", "voc_result": voc_result.data, "step_log": step_log}

    step_log.append(build_step_log_entry("voc_refresh", "completed", "No queries to process"))
    return {"status": "completed", "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_landing_page_diff")
def run_landing_page_diff(
    account_id: str = "",
    urls: list[str] | None = None,
) -> dict[str, Any]:
    """Re-crawl landing pages and detect changes via Scrapling."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_landing_page_diff_async(account_id, urls or [])
    )


async def _run_landing_page_diff_async(
    account_id: str,
    urls: list[str],
) -> dict[str, Any]:
    step_log: list[dict] = []
    step_log.append(build_step_log_entry("landing_page_diff", "started"))

    if not urls:
        step_log.append(build_step_log_entry("landing_page_diff", "skipped", "No URLs"))
        return {"status": "skipped", "step_log": step_log}

    changes: list[dict[str, Any]] = []

    try:
        from app.services.acquisition.connectors.web_scraper import web_scraper

        for url in urls:
            result = await web_scraper.monitor_competitor_page(url)
            if result.changed:
                changes.append({
                    "url": url,
                    "changed": True,
                    "content_preview": (result.current_content or "")[:500],
                })

    except Exception as exc:
        logger.error("landing_page_diff.failed error=%s", exc)

    step_log.append(build_step_log_entry("landing_page_diff", "completed",
                                         f"{len(changes)} pages changed"))
    return {"status": "completed", "changes": changes, "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_news_monitor")
def run_news_monitor(
    account_id: str = "",
    offer_id: str = "",
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Search for news and developments via Scrapling web search."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_news_monitor_async(account_id, offer_id, keywords or [])
    )


async def _run_news_monitor_async(
    account_id: str,
    offer_id: str,
    keywords: list[str],
) -> dict[str, Any]:
    from app.services.hindsight.banks import BankType
    from app.services.hindsight.memory import retain_observation

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("news_monitor", "started"))

    if not keywords:
        step_log.append(build_step_log_entry("news_monitor", "skipped", "No keywords"))
        return {"status": "skipped", "step_log": step_log}

    findings: list[dict[str, Any]] = []

    try:
        from app.services.acquisition.connectors.web_scraper import web_scraper

        for keyword in keywords:
            results = await web_scraper.search_web(query=keyword, max_results=5)
            for r in results:
                findings.append({
                    "keyword": keyword,
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                })

                # Retain news findings to RESEARCH bank
                if account_id:
                    await retain_observation(
                        account_id=account_id,
                        bank_type=BankType.RESEARCH,
                        content=f"News: {r.title}. {r.snippet}",
                        offer_id=offer_id or None,
                        source_type="news",
                        source_url=r.url,
                        evidence_type="news_finding",
                        confidence_score=0.5,
                    )

    except Exception as exc:
        logger.error("news_monitor.failed error=%s", exc)

    step_log.append(build_step_log_entry("news_monitor", "completed",
                                         f"{len(findings)} findings"))
    return {"status": "completed", "findings": findings, "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_literature_refresh")
def run_literature_refresh() -> dict[str, Any]:
    """Update health or science-backed evidence."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_run_literature_refresh_async())


async def _run_literature_refresh_async() -> dict[str, Any]:
    from app.workers.domain_research import DomainResearchWorker

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("literature_refresh", "started"))

    # In production, iterate active health/supplement offers
    step_log.append(build_step_log_entry("literature_refresh", "completed",
                                         "Placeholder — needs active offer iteration"))

    return {"status": "completed", "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_performance_ingest")
def run_performance_ingest(
    account_id: str = "",
    offer_id: str = "",
    performance_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest ad performance data and connect outcomes to strategic objects."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _run_performance_ingest_async(account_id, offer_id, performance_data or {})
    )


async def _run_performance_ingest_async(
    account_id: str,
    offer_id: str,
    performance_data: dict[str, Any],
) -> dict[str, Any]:
    from app.services.hindsight.banks import BankType
    from app.services.hindsight.memory import retain_observation

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("performance_ingest", "started"))

    if not performance_data or not account_id:
        step_log.append(build_step_log_entry("performance_ingest", "skipped", "No data"))
        return {"status": "skipped", "step_log": step_log}

    retained_count = 0

    # Ingest per-asset performance metrics
    for asset_id, metrics in performance_data.get("assets", {}).items():
        perf_text = (
            f"Performance ({asset_id}): "
            f"Spend=${metrics.get('spend', 0):.2f}, "
            f"Impressions={metrics.get('impressions', 0)}, "
            f"Clicks={metrics.get('clicks', 0)}, "
            f"CTR={metrics.get('ctr', 0):.2%}, "
            f"CPA=${metrics.get('cpa', 0):.2f}, "
            f"ROAS={metrics.get('roas', 0):.2f}."
        )
        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=perf_text,
            offer_id=offer_id or None,
            source_type="performance",
            evidence_type="performance_signal",
            confidence_score=0.95,
            extra_metadata={"asset_id": asset_id, **metrics},
        )
        retained_count += 1

    step_log.append(build_step_log_entry("performance_ingest", "completed",
                                         f"Retained {retained_count} performance records"))
    return {"status": "completed", "retained_count": retained_count, "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_memory_reflection")
def run_memory_reflection() -> dict[str, Any]:
    """Generate candidate durable lessons across all active accounts."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_run_memory_reflection_async())


async def _run_memory_reflection_async() -> dict[str, Any]:
    from app.workers.memory_reflection import MemoryReflectionWorker

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("memory_reflection", "started"))

    # In production, iterate all active accounts and trigger reflection
    step_log.append(build_step_log_entry("memory_reflection", "completed",
                                         "Placeholder — needs active account iteration"))

    return {"status": "completed", "step_log": step_log}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_iteration_synthesis")
def run_iteration_synthesis() -> dict[str, Any]:
    """Create next-draft targets and test backlog."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_run_iteration_synthesis_async())


async def _run_iteration_synthesis_async() -> dict[str, Any]:
    from app.workers.iteration_planner import IterationPlannerWorker

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("iteration_synthesis", "started"))

    # In production, iterate active offers with recent performance data
    step_log.append(build_step_log_entry("iteration_synthesis", "completed",
                                         "Placeholder — needs active offer iteration"))

    return {"status": "completed", "step_log": step_log}

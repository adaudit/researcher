"""Weekly research and reflection workflow tasks.

The weekly cycle is where the architecture earns its value:
  retain -> recall -> reflect -> publish

Jobs:
  - Top ad refresh (weekly)
  - Comments/reviews refresh (weekly)
  - Landing page diff (weekly)
  - News monitor (daily)
  - Literature refresh (weekly)
  - Performance feedback ingest (daily)
  - Memory reflection (weekly)
  - Iteration synthesis (weekly)
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app

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
def run_voc_refresh() -> dict[str, Any]:
    """Detect new pains, objections, and language shifts."""
    logger.info("weekly.voc_refresh started")
    return {"status": "completed", "detail": "VOC refresh placeholder"}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_landing_page_diff")
def run_landing_page_diff() -> dict[str, Any]:
    """Detect changes in headlines, proof, offer, CTA, and structure."""
    logger.info("weekly.landing_page_diff started")
    return {"status": "completed", "detail": "Landing page diff placeholder"}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_news_monitor")
def run_news_monitor() -> dict[str, Any]:
    """Detect events changing sensitivity or angle relevance."""
    logger.info("daily.news_monitor started")
    return {"status": "completed", "detail": "News monitor placeholder"}


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
def run_performance_ingest() -> dict[str, Any]:
    """Connect outcomes to strategic objects."""
    logger.info("daily.performance_ingest started")
    return {"status": "completed", "detail": "Performance ingest placeholder"}


@celery_app.task(name="app.orchestrator.workflows.weekly_refresh.run_memory_reflection")
def run_memory_reflection() -> dict[str, Any]:
    """Generate candidate durable lessons across all active accounts."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_run_memory_reflection_async())


async def _run_memory_reflection_async() -> dict[str, Any]:
    from app.workers.memory_reflection import MemoryReflectionWorker
    from app.workers.base import WorkerInput

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
    from app.workers.base import WorkerInput

    step_log: list[dict] = []
    step_log.append(build_step_log_entry("iteration_synthesis", "started"))

    # In production, iterate active offers with recent performance data
    step_log.append(build_step_log_entry("iteration_synthesis", "completed",
                                         "Placeholder — needs active offer iteration"))

    return {"status": "completed", "step_log": step_log}

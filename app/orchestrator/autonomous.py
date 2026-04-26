"""Autonomous agentic orchestrator — the system that runs itself.

This is the meta-agent. It doesn't create ads directly — it decides
WHAT to do based on the current state of the account, then delegates
to the appropriate workers and workflows.

Scheduled cycles:
  - Hourly:  check for new performance data → trigger learning
  - Daily:   news monitor, competitor scan, new styles scan
  - Weekly:  full ideation cycle, coverage matrix, reflection, VOC refresh
  - Monthly: cross-business aggregation, skill pruning, primer audit

The agentic loop:
  1. SENSE — What's the current state? What data is new?
  2. DECIDE — What's the highest-leverage action right now?
  3. ACT — Execute the chosen workflow/worker
  4. LEARN — Update skills, primers, and global brain from results
"""

from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.engine import build_step_log_entry, celery_app
from app.workers.base import WorkerInput

logger = logging.getLogger(__name__)


# ── Hourly: Performance Learning Loop ────────────────────────────────

@celery_app.task(name="autonomous.hourly_learning")
def hourly_learning_loop() -> dict[str, Any]:
    """Check for new performance data and trigger skill/primer updates.

    Runs every hour. Lightweight — only processes if new data exists.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _hourly_learning_async()
    )


async def _hourly_learning_async() -> dict[str, Any]:
    """Process any new performance data through the learning loop."""
    from sqlalchemy import select
    from app.db.models.creative import CreativeAsset
    from app.db.session import async_session_factory
    from app.services.intelligence.skill_manager import SkillDomain, skill_manager

    step_log = [build_step_log_entry("hourly_learning", "started")]
    updates = 0

    async with async_session_factory() as db:
        # Find recently updated assets with performance data but not yet learned
        stmt = (
            select(CreativeAsset)
            .where(
                CreativeAsset.performance_tier.isnot(None),
                CreativeAsset.performance_tier != "untested",
                CreativeAsset.processing_status != "learned",
            )
            .order_by(CreativeAsset.updated_at.desc())
            .limit(50)
        )
        result = await db.execute(stmt)
        assets = list(result.scalars().all())

        for asset in assets:
            try:
                attrs = {
                    "hook_type": asset.hook_type,
                    "format_type": asset.format_type,
                    "visual_style": asset.visual_style,
                    "awareness_level": asset.awareness_level,
                }
                perf = {
                    "roas": asset.roas or 0,
                    "ctr": asset.ctr or 0,
                    "cpa": asset.cpa or 0,
                    "tier": asset.performance_tier,
                }
                for domain in [SkillDomain.HOOKS, SkillDomain.VISUALS, SkillDomain.COPY]:
                    await skill_manager.learn_from_performance(
                        asset.account_id, domain, perf, attrs,
                    )
                asset.processing_status = "learned"
                updates += 1
            except Exception as exc:
                # Hourly learning is the self-learning loop — failures
                # mean skills are stale. Log at warning so production
                # cron failures are surfaced.
                logger.warning(
                    "hourly.learn_failed asset=%s account=%s error=%s",
                    asset.id, asset.account_id, exc,
                )

        if updates:
            await db.commit()

    step_log.append(build_step_log_entry("hourly_learning", "completed",
                                         f"Processed {updates} assets"))
    return {"status": "completed", "updates": updates, "step_log": step_log}


# ── Daily: Proactive Research ──────────────────────────────────────

@celery_app.task(name="autonomous.daily_research")
def daily_research() -> dict[str, Any]:
    """Daily proactive research cycle: news, competitors, new styles."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _daily_research_async()
    )


async def _daily_research_async() -> dict[str, Any]:
    """Run daily research for all active accounts."""
    from sqlalchemy import select
    from app.db.models.account import Account
    from app.db.models.offer import Offer
    from app.db.session import async_session_factory

    step_log = [build_step_log_entry("daily_research", "started")]

    async with async_session_factory() as db:
        # Get all active accounts with offers
        stmt = select(Account).where(Account.is_active == True)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())

        for account in accounts:
            offer_stmt = select(Offer).where(
                Offer.account_id == account.id,
                Offer.status == "active",
            )
            offer_result = await db.execute(offer_stmt)
            offers = list(offer_result.scalars().all())

            for offer in offers:
                try:
                    # News monitor
                    from app.orchestrator.workflows.weekly_refresh import _run_news_monitor_async
                    keywords = [offer.mechanism or "", offer.name or ""]
                    keywords = [k for k in keywords if k]
                    if keywords:
                        await _run_news_monitor_async(account.id, offer.id, keywords[:3])

                    # New styles scan
                    await _scan_new_styles(account.id, offer.id)

                except Exception as exc:
                    # Daily research drives proactive intelligence —
                    # silent failures degrade insight quality.
                    logger.warning(
                        "daily.research_failed account=%s offer=%s error=%s",
                        account.id, offer.id, exc,
                    )

    step_log.append(build_step_log_entry("daily_research", "completed"))
    return {"status": "completed", "step_log": step_log}


async def _scan_new_styles(account_id: str, offer_id: str) -> dict[str, Any]:
    """Scan for emerging creative styles and formats (STORMING "N").

    What to look for:
    - New ad formats trending on TikTok/Instagram (structural innovation)
    - Visual styles gaining traction (AI-generated, new camera angles, etc.)
    - Content formats that didn't exist 6 months ago
    - Cross-platform format migrations (TikTok style → Meta ads)

    How to discover:
    - ScrapCreators: pull recent high-engagement ads, filter for unusual formats
    - Organic: pull trending content, look for structural patterns
    - Compare against known template categories — flag unknowns
    """
    from app.services.hindsight.memory import retain_observation

    try:
        from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
        from app.services.llm.router import Capability, router

        # Pull recent trending content from TikTok
        result = await scrapecreators_client.tiktok.search_videos(
            query="ad creative new format", count=20,
        )

        if not result.data:
            return {"styles_found": 0}

        import json
        content_text = json.dumps(result.data[:15], indent=1, default=str)[:8000]

        # LLM analysis: identify styles that DON'T match existing templates
        analysis = await router.generate(
            capability=Capability.TEXT_EXTRACTION,
            system_prompt=(
                "You are a Creative Format Scout. Analyze trending content and identify "
                "NEW ad formats or visual styles that are EMERGING — not established.\n\n"
                "Known formats (DO NOT report these): headline+image, before_after, infographic, "
                "testimonial_card, meme_style, screenshot_chat, ugc_selfie, note_from_founder, "
                "scientific_study, comparison_chart, talking_head, listicle_video, green_screen.\n\n"
                "Look for:\n"
                "- Structural innovations (new ways to organize content)\n"
                "- Visual innovations (new aesthetics, camera techniques, AI-generated styles)\n"
                "- Format migrations (something that worked on one platform appearing on another)\n"
                "- Hybrid formats (combinations of existing formats that create something new)\n\n"
                "For each new style found, describe: what it looks like, why it's different, "
                "which platform it's trending on, and how it could be adapted for ads."
            ),
            user_prompt=f"Analyze this trending content for NEW emerging styles:\n\n{content_text}",
            temperature=0.3,
            max_tokens=3000,
            json_schema={
                "type": "object",
                "properties": {
                    "new_styles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "platform": {"type": "string"},
                                "how_to_adapt": {"type": "string"},
                                "novelty_score": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        )

        # Retain new styles as seeds
        styles = analysis.get("new_styles", [])
        for style in styles:
            if style.get("novelty_score", 0) >= 6:
                await retain_observation(
                    account_id=account_id,
                    bank_type=BankType.SEEDS,
                    content=(
                        f"New style discovered: {style.get('name', '')}. "
                        f"{style.get('description', '')}. "
                        f"How to adapt: {style.get('how_to_adapt', '')}."
                    ),
                    offer_id=offer_id,
                    source_type="new_style_scan",
                    evidence_type="ideation_seed",
                    confidence_score=0.5,
                    extra_metadata={"seed_source": "new_style", "platform": style.get("platform")},
                )

        return {"styles_found": len(styles)}

    except Exception as exc:
        logger.debug("new_styles.scan_failed error=%s", exc)
        return {"styles_found": 0, "error": str(exc)}


# ── Weekly: Full Cycle ──────────────────────────────────────────────

@celery_app.task(name="autonomous.weekly_full_cycle")
def weekly_full_cycle() -> dict[str, Any]:
    """Weekly full creative cycle for all active accounts.

    For each account with active offers:
    1. VOC refresh (pull fresh comments/reviews)
    2. Competitor scan (fresh swipes)
    3. Landing page diff
    4. Coverage matrix analysis
    5. Memory reflection
    6. Auto-primer update
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _weekly_full_cycle_async()
    )


async def _weekly_full_cycle_async() -> dict[str, Any]:
    from sqlalchemy import select
    from app.db.models.account import Account
    from app.db.session import async_session_factory

    step_log = [build_step_log_entry("weekly_cycle", "started")]
    accounts_processed = 0

    async with async_session_factory() as db:
        stmt = select(Account).where(Account.is_active == True)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())

        for account in accounts:
            try:
                # Run memory reflection
                from app.workers.memory_reflection import MemoryReflectionWorker
                reflection_worker = MemoryReflectionWorker()
                await reflection_worker.run(WorkerInput(
                    account_id=account.id,
                    params={
                        "reflection_prompt": (
                            "Weekly reflection: analyze all evidence accumulated this week. "
                            "What patterns are emerging? What should we double down on? "
                            "What should we stop doing?"
                        ),
                    },
                ))

                accounts_processed += 1

            except Exception as exc:
                # Weekly reflection is when durable lessons get distilled —
                # a silent failure here means the account misses a learning
                # cycle. Surface at warning.
                logger.warning(
                    "weekly.account_failed account=%s error=%s",
                    account.id, exc,
                )

    step_log.append(build_step_log_entry("weekly_cycle", "completed",
                                         f"Processed {accounts_processed} accounts"))
    return {"status": "completed", "accounts": accounts_processed, "step_log": step_log}


# ── Weekly: Cultural Pulse ────────────────────────────────────────

@celery_app.task(name="autonomous.weekly_cultural_pulse")
def weekly_cultural_pulse() -> dict[str, Any]:
    """Weekly cultural scan — runs before the full cycle so ideation
    has fresh cultural context (trending concerns, media effects, etc.)."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _weekly_cultural_pulse_async()
    )


async def _weekly_cultural_pulse_async() -> dict[str, Any]:
    from sqlalchemy import select
    from app.db.models.account import Account
    from app.db.models.offer import Offer
    from app.db.session import async_session_factory
    from app.workers.cultural_pulse import CulturalPulseWorker

    step_log = [build_step_log_entry("cultural_pulse", "started")]
    scanned = 0

    async with async_session_factory() as db:
        stmt = select(Account).where(Account.is_active == True)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())

        for account in accounts:
            offer_stmt = select(Offer).where(
                Offer.account_id == account.id,
                Offer.status == "active",
            )
            offer_result = await db.execute(offer_stmt)
            offers = list(offer_result.scalars().all())

            for offer in offers:
                try:
                    worker = CulturalPulseWorker()
                    await worker.run(WorkerInput(
                        account_id=account.id,
                        offer_id=offer.id,
                        params={
                            "niche_keywords": [
                                k for k in [
                                    offer.mechanism or "",
                                    offer.name or "",
                                    getattr(offer, "target_audience", "") or "",
                                ] if k
                            ],
                        },
                    ))
                    scanned += 1
                except Exception as exc:
                    logger.warning(
                        "cultural_pulse.scan_failed account=%s offer=%s error=%s",
                        account.id, offer.id, exc,
                    )

    step_log.append(build_step_log_entry(
        "cultural_pulse", "completed", f"Scanned {scanned} offers",
    ))
    return {"status": "completed", "scanned": scanned, "step_log": step_log}


# ── Monthly: Cross-Business Learning ─────────────────────────────

@celery_app.task(name="autonomous.monthly_cross_business")
def monthly_cross_business() -> dict[str, Any]:
    """Monthly cross-business intelligence aggregation.

    Pulls learnings from all accounts, finds universal patterns,
    promotes confirmed patterns to the global brain.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _monthly_cross_business_async()
    )


async def _monthly_cross_business_async() -> dict[str, Any]:
    from sqlalchemy import select
    from app.db.models.account import Account
    from app.db.session import async_session_factory
    from app.services.intelligence.global_brain import global_brain

    step_log = [build_step_log_entry("cross_business", "started")]

    async with async_session_factory() as db:
        stmt = select(Account.id).where(Account.is_active == True)
        result = await db.execute(stmt)
        account_ids = [row[0] for row in result.all()]

    if len(account_ids) >= 3:
        aggregation = await global_brain.aggregate_reflections(account_ids)
        patterns = len(aggregation.get("patterns", []))
        step_log.append(build_step_log_entry("cross_business", "completed",
                                             f"Aggregated {len(account_ids)} accounts, {patterns} patterns"))
    else:
        step_log.append(build_step_log_entry("cross_business", "skipped",
                                             f"Need 3+ accounts, have {len(account_ids)}"))

    return {"status": "completed", "step_log": step_log}


# ── Import for SEEDS bank type ────────────────────────────────────
from app.services.hindsight.banks import BankType


# ── Celery Beat Schedule ──────────────────────────────────────────

AUTONOMOUS_SCHEDULE = {
    "hourly-learning": {
        "task": "autonomous.hourly_learning",
        "schedule": 3600.0,  # every hour
    },
    "daily-research": {
        "task": "autonomous.daily_research",
        "schedule": 86400.0,  # every 24 hours
    },
    "weekly-full-cycle": {
        "task": "autonomous.weekly_full_cycle",
        "schedule": 604800.0,  # every 7 days
    },
    "monthly-cross-business": {
        "task": "autonomous.monthly_cross_business",
        "schedule": 2592000.0,  # every 30 days
    },
}

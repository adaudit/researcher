"""Performance Intelligence API — rich metrics ingest with intelligent questions.

The real performance system. Handles first-party (Meta Ads Manager, GA4,
pixel, CRM) and third-party (Ad Audit, Bulk Launcher) metrics with full
demographic, geographic, placement, and audience targeting breakdowns.

The system asks clarifying questions when data is ambiguous or anomalous.
Answers become rules for future ingests — the system learns how YOUR
data works.

POST   /v1/performance/snapshots              — bulk daily snapshot ingest
POST   /v1/performance/demographics            — demographic breakdown ingest
POST   /v1/performance/audience-targeting      — audience targeting config ingest
GET    /v1/performance/snapshots/{ad_id}       — get performance history for an ad
GET    /v1/performance/questions               — pending clarifying questions
POST   /v1/performance/questions/{id}/answer   — answer a question
GET    /v1/performance/winning-definition      — get winning thresholds
PUT    /v1/performance/winning-definition      — update winning thresholds
GET    /v1/performance/benchmarks/{industry}   — get industry benchmarks
POST   /v1/performance/sync-learning           — trigger learning loop from perf data
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.performance import (
    AudienceTargeting,
    DemographicBreakdown,
    IngestQuestion,
    PerformanceSnapshot,
    WinningDefinition,
)
from app.db.session import get_db
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request/Response schemas ────────────────────────────────────────

class SnapshotRecord(BaseModel):
    """One daily performance record for an ad."""

    external_ad_id: str
    external_adset_id: str | None = None
    external_campaign_id: str | None = None
    ad_name: str | None = None
    adset_name: str | None = None
    campaign_name: str | None = None

    date: str = Field(..., description="YYYY-MM-DD")
    data_source: str = Field("meta_first_party", description="meta_first_party | ga4 | pixel | crm | ad_audit | bulk_launcher")
    platform: str = Field("meta")

    # First-party
    spend: float | None = None
    impressions: int | None = None
    reach: int | None = None
    frequency: float | None = None
    clicks: int | None = None
    link_clicks: int | None = None

    # Engagement
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None

    # Video
    video_plays: int | None = None
    video_plays_25: int | None = None
    video_plays_50: int | None = None
    video_plays_75: int | None = None
    video_plays_100: int | None = None
    avg_watch_time_seconds: float | None = None
    thumb_stop_ratio: float | None = None
    hook_rate: float | None = None

    # Conversions
    purchases: int | None = None
    purchase_value: float | None = None
    add_to_carts: int | None = None
    initiates_checkout: int | None = None
    leads: int | None = None

    # Third-party (Ad Audit / Bulk Launcher)
    tp_purchases: int | None = None
    tp_revenue: float | None = None
    tp_roas: float | None = None
    tp_cpa: float | None = None
    tp_new_customer_purchases: int | None = None
    tp_new_customer_revenue: float | None = None
    tp_attribution_model: str | None = None

    # Landing page
    landing_page_views: int | None = None
    bounce_rate: float | None = None

    # Status
    is_active: bool | None = None

    # Creative content for matching
    headline: str | None = None
    body_copy: str | None = None

    # Pass through any extra fields
    extra: dict | None = None


class DemographicRecord(BaseModel):
    external_ad_id: str
    snapshot_id: str | None = None
    age_range: str | None = None
    gender: str | None = None
    state: str | None = None
    dma: str | None = None
    country: str | None = None
    device: str | None = None
    placement: str | None = None
    spend: float | None = None
    impressions: int | None = None
    clicks: int | None = None
    conversions: int | None = None
    revenue: float | None = None


class AudienceTargetingRecord(BaseModel):
    external_adset_id: str
    targeting_type: str | None = None
    interests: list[str] | None = None
    lookalike_source: str | None = None
    lookalike_percentage: float | None = None
    custom_audience_name: str | None = None
    custom_audience_type: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    genders: list[str] | None = None
    locations: list[str] | None = None
    placements: list[str] | None = None
    optimization_goal: str | None = None
    bid_strategy: str | None = None
    daily_budget: float | None = None
    raw_targeting: dict | None = None


class SnapshotIngestRequest(BaseModel):
    offer_id: str | None = None
    data_source: str = "meta_first_party"
    records: list[SnapshotRecord]


class DemographicIngestRequest(BaseModel):
    records: list[DemographicRecord]


class AudienceTargetingIngestRequest(BaseModel):
    offer_id: str | None = None
    records: list[AudienceTargetingRecord]


class WinningDefinitionRequest(BaseModel):
    primary_metric: str = "roas"
    winner_threshold: float = 3.0
    strong_threshold: float = 2.0
    average_threshold: float = 1.0
    weak_threshold: float = 0.5
    min_spend_for_evaluation: float = 50.0
    min_impressions_for_evaluation: int = 1000
    min_days_running: int = 3
    attribution_source: str = "first_party"
    auto_calibrate: bool = True
    notes: str | None = None


class QuestionAnswer(BaseModel):
    answer: str
    creates_rule: bool = False
    rule_description: str | None = None


class IngestResponse(BaseModel):
    ingested: int
    questions_generated: int
    anomalies_flagged: int


# ── Snapshot Ingest ─────────────────────────────────────────────────

@router.post("/snapshots", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_snapshots(
    body: SnapshotIngestRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest daily performance snapshots.

    Calculates derived metrics, classifies performance tiers,
    flags anomalies, and generates clarifying questions.
    """
    questions = 0
    anomalies = 0

    # Load winning definition for tier classification
    win_def = await _get_winning_definition(db, account_id, body.offer_id)

    for record in body.records:
        snapshot_id = f"ps_{uuid4().hex[:12]}"

        # Calculate derived metrics
        ctr = _safe_div(record.clicks, record.impressions) if record.clicks and record.impressions else record.ctr if hasattr(record, 'ctr') else None
        cpc = _safe_div(record.spend, record.clicks) if record.spend and record.clicks else None
        cpm = _safe_div(record.spend, record.impressions, 1000) if record.spend and record.impressions else None
        cpa = _safe_div(record.spend, record.purchases) if record.spend and record.purchases else None
        roas = _safe_div(record.purchase_value, record.spend) if record.purchase_value and record.spend else None
        aov = _safe_div(record.purchase_value, record.purchases) if record.purchase_value and record.purchases else None

        # Classify tier
        tier = _classify_tier(
            metric_value=roas if win_def.primary_metric == "roas" else cpa,
            win_def=win_def,
            spend=record.spend,
            impressions=record.impressions,
        )

        snapshot = PerformanceSnapshot(
            id=snapshot_id,
            account_id=account_id,
            offer_id=body.offer_id,
            external_ad_id=record.external_ad_id,
            external_adset_id=record.external_adset_id,
            external_campaign_id=record.external_campaign_id,
            ad_name=record.ad_name,
            adset_name=record.adset_name,
            campaign_name=record.campaign_name,
            date=record.date,
            data_source=record.data_source or body.data_source,
            platform=record.platform,
            spend=record.spend,
            impressions=record.impressions,
            reach=record.reach,
            frequency=record.frequency,
            clicks=record.clicks,
            link_clicks=record.link_clicks,
            likes=record.likes,
            comments=record.comments,
            shares=record.shares,
            saves=record.saves,
            video_plays=record.video_plays,
            video_plays_25=record.video_plays_25,
            video_plays_50=record.video_plays_50,
            video_plays_75=record.video_plays_75,
            video_plays_100=record.video_plays_100,
            avg_watch_time_seconds=record.avg_watch_time_seconds,
            thumb_stop_ratio=record.thumb_stop_ratio,
            hook_rate=record.hook_rate,
            purchases=record.purchases,
            purchase_value=record.purchase_value,
            add_to_carts=record.add_to_carts,
            initiates_checkout=record.initiates_checkout,
            leads=record.leads,
            tp_purchases=record.tp_purchases,
            tp_revenue=record.tp_revenue,
            tp_roas=record.tp_roas,
            tp_cpa=record.tp_cpa,
            tp_new_customer_purchases=record.tp_new_customer_purchases,
            tp_new_customer_revenue=record.tp_new_customer_revenue,
            tp_attribution_model=record.tp_attribution_model,
            landing_page_views=record.landing_page_views,
            bounce_rate=record.bounce_rate,
            ctr=ctr,
            cpc=cpc,
            cpm=cpm,
            cpa=cpa,
            roas=roas,
            aov=aov,
            is_active=record.is_active,
            performance_tier=tier,
            raw_data=record.extra,
        )
        db.add(snapshot)

        # Anomaly detection — flag things that look wrong
        if record.spend and record.spend > 0 and record.impressions == 0:
            await _create_question(
                db, account_id, record.data_source,
                "impressions", str(record.impressions),
                f"Ad '{record.ad_name or record.external_ad_id}' shows ${record.spend:.2f} spend but 0 impressions on {record.date}. Is this data correct or a reporting delay?",
                "anomaly",
            )
            anomalies += 1
            questions += 1

        if record.tp_roas and roas and abs(record.tp_roas - roas) / max(roas, 0.01) > 1.0:
            await _create_question(
                db, account_id, record.data_source,
                "roas_discrepancy", f"fp={roas:.2f} tp={record.tp_roas:.2f}",
                f"Ad '{record.ad_name or record.external_ad_id}': First-party ROAS is {roas:.2f} but third-party reports {record.tp_roas:.2f}. Which should we use as source of truth for this account?",
                "metric_definition",
                options=["first_party", "third_party", "blended_average"],
            )
            questions += 1

        # Retain performance signal to Hindsight
        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=(
                f"Performance {record.date} ({record.external_ad_id}): "
                f"Tier={tier}, Spend=${record.spend or 0:.2f}, "
                f"ROAS={roas or 0:.2f}, CPA=${cpa or 0:.2f}, "
                f"CTR={ctr or 0:.2%}, Hook={record.hook_rate or 0:.1%}. "
                f"{'3P ROAS=' + str(record.tp_roas) if record.tp_roas else ''}"
            ),
            offer_id=body.offer_id,
            source_type="performance",
            evidence_type="performance_signal",
            confidence_score=0.95,
            extra_metadata={"ad_id": record.external_ad_id, "tier": tier, "date": record.date},
        )

    await db.commit()

    return IngestResponse(
        ingested=len(body.records),
        questions_generated=questions,
        anomalies_flagged=anomalies,
    )


# ── Demographic Breakdown Ingest ────────────────────────────────────

@router.post("/demographics", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_demographics(
    body: DemographicIngestRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest demographic breakdowns for ads."""
    for record in body.records:
        ctr = _safe_div(record.clicks, record.impressions) if record.clicks and record.impressions else None
        cpa = _safe_div(record.spend, record.conversions) if record.spend and record.conversions else None
        roas = _safe_div(record.revenue, record.spend) if record.revenue and record.spend else None

        breakdown = DemographicBreakdown(
            id=f"db_{uuid4().hex[:12]}",
            account_id=account_id,
            snapshot_id=record.snapshot_id or "",
            external_ad_id=record.external_ad_id,
            age_range=record.age_range,
            gender=record.gender,
            state=record.state,
            dma=record.dma,
            country=record.country,
            device=record.device,
            placement=record.placement,
            spend=record.spend,
            impressions=record.impressions,
            clicks=record.clicks,
            conversions=record.conversions,
            revenue=record.revenue,
            ctr=ctr,
            cpa=cpa,
            roas=roas,
        )
        db.add(breakdown)

    await db.commit()
    return IngestResponse(ingested=len(body.records), questions_generated=0, anomalies_flagged=0)


# ── Audience Targeting Ingest ───────────────────────────────────────

@router.post("/audience-targeting", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_audience_targeting(
    body: AudienceTargetingIngestRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest audience targeting configurations."""
    for record in body.records:
        targeting = AudienceTargeting(
            id=f"at_{uuid4().hex[:12]}",
            account_id=account_id,
            offer_id=body.offer_id,
            external_adset_id=record.external_adset_id,
            targeting_type=record.targeting_type,
            interests=record.interests,
            lookalike_source=record.lookalike_source,
            lookalike_percentage=record.lookalike_percentage,
            custom_audience_name=record.custom_audience_name,
            custom_audience_type=record.custom_audience_type,
            age_min=record.age_min,
            age_max=record.age_max,
            genders=record.genders,
            locations=record.locations,
            placements=record.placements,
            optimization_goal=record.optimization_goal,
            bid_strategy=record.bid_strategy,
            daily_budget=record.daily_budget,
            raw_targeting=record.raw_targeting,
        )
        db.add(targeting)

    await db.commit()
    return IngestResponse(ingested=len(body.records), questions_generated=0, anomalies_flagged=0)


# ── Performance History ─────────────────────────────────────────────

@router.get("/snapshots/{external_ad_id}")
async def get_performance_history(
    external_ad_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    data_source: str | None = Query(None),
    limit: int = Query(90, le=365),
) -> list[dict]:
    """Get daily performance history for a specific ad."""
    conditions = [
        PerformanceSnapshot.account_id == account_id,
        PerformanceSnapshot.external_ad_id == external_ad_id,
    ]
    if data_source:
        conditions.append(PerformanceSnapshot.data_source == data_source)

    stmt = (
        select(PerformanceSnapshot)
        .where(and_(*conditions))
        .order_by(PerformanceSnapshot.date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    return [
        {
            "date": str(s.date),
            "spend": s.spend,
            "impressions": s.impressions,
            "clicks": s.clicks,
            "ctr": s.ctr,
            "cpa": s.cpa,
            "roas": s.roas,
            "hook_rate": s.hook_rate,
            "tp_roas": s.tp_roas,
            "tp_cpa": s.tp_cpa,
            "performance_tier": s.performance_tier,
            "purchases": s.purchases,
            "purchase_value": s.purchase_value,
            "data_source": s.data_source,
        }
        for s in snapshots
    ]


# ── Intelligent Questions ───────────────────────────────────────────

@router.get("/questions")
async def list_questions(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    status_filter: str = Query("pending"),
) -> list[dict]:
    """List pending clarifying questions about ingested data."""
    stmt = (
        select(IngestQuestion)
        .where(
            IngestQuestion.account_id == account_id,
            IngestQuestion.status == status_filter,
        )
        .order_by(IngestQuestion.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": q.id,
            "question": q.question,
            "question_type": q.question_type,
            "related_field": q.related_field,
            "related_value": q.related_value,
            "options": q.options,
            "status": q.status,
            "data_source": q.data_source,
        }
        for q in result.scalars()
    ]


@router.post("/questions/{question_id}/answer")
async def answer_question(
    question_id: str,
    body: QuestionAnswer,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Answer a clarifying question. Optionally create a rule for future ingests."""
    stmt = select(IngestQuestion).where(
        IngestQuestion.id == question_id,
        IngestQuestion.account_id == account_id,
    )
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.answer = body.answer
    question.status = "answered"
    question.creates_rule = body.creates_rule
    question.rule_description = body.rule_description

    # If creating a rule, apply it to winning definition
    if body.creates_rule and question.question_type == "metric_definition":
        if body.answer in ("first_party", "third_party", "blended_average"):
            win_def = await _get_winning_definition(db, account_id)
            win_def.attribution_source = body.answer
            logger.info("performance.rule_applied attribution_source=%s", body.answer)

    await db.commit()
    return {"status": "answered", "creates_rule": body.creates_rule}


# ── Winning Definition ──────────────────────────────────────────────

@router.get("/winning-definition")
async def get_winning_definition(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    offer_id: str | None = Query(None),
) -> dict:
    """Get the winning definition thresholds for this account."""
    win_def = await _get_winning_definition(db, account_id, offer_id)
    return {
        "primary_metric": win_def.primary_metric,
        "winner_threshold": win_def.winner_threshold,
        "strong_threshold": win_def.strong_threshold,
        "average_threshold": win_def.average_threshold,
        "weak_threshold": win_def.weak_threshold,
        "min_spend_for_evaluation": win_def.min_spend_for_evaluation,
        "min_impressions_for_evaluation": win_def.min_impressions_for_evaluation,
        "min_days_running": win_def.min_days_running,
        "attribution_source": win_def.attribution_source,
        "auto_calibrate": win_def.auto_calibrate,
        "industry": win_def.industry,
        "industry_avg_cpa": win_def.industry_avg_cpa,
        "industry_avg_roas": win_def.industry_avg_roas,
        "industry_avg_ctr": win_def.industry_avg_ctr,
    }


@router.put("/winning-definition")
async def update_winning_definition(
    body: WinningDefinitionRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    offer_id: str | None = Query(None),
) -> dict:
    """Update winning definition thresholds."""
    win_def = await _get_winning_definition(db, account_id, offer_id)
    win_def.primary_metric = body.primary_metric
    win_def.winner_threshold = body.winner_threshold
    win_def.strong_threshold = body.strong_threshold
    win_def.average_threshold = body.average_threshold
    win_def.weak_threshold = body.weak_threshold
    win_def.min_spend_for_evaluation = body.min_spend_for_evaluation
    win_def.min_impressions_for_evaluation = body.min_impressions_for_evaluation
    win_def.min_days_running = body.min_days_running
    win_def.attribution_source = body.attribution_source
    win_def.auto_calibrate = body.auto_calibrate
    win_def.notes = body.notes
    await db.commit()
    return {"status": "updated"}


# ── Industry Benchmarks ─────────────────────────────────────────────

INDUSTRY_BENCHMARKS: dict[str, dict[str, float]] = {
    "supplements": {"avg_cpa": 45.0, "avg_roas": 2.8, "avg_ctr": 0.018, "avg_hook_rate": 0.35},
    "skincare": {"avg_cpa": 38.0, "avg_roas": 3.2, "avg_ctr": 0.022, "avg_hook_rate": 0.38},
    "fitness": {"avg_cpa": 52.0, "avg_roas": 2.5, "avg_ctr": 0.015, "avg_hook_rate": 0.32},
    "ecommerce_general": {"avg_cpa": 35.0, "avg_roas": 3.5, "avg_ctr": 0.02, "avg_hook_rate": 0.30},
    "saas": {"avg_cpa": 120.0, "avg_roas": 5.0, "avg_ctr": 0.012, "avg_hook_rate": 0.25},
    "financial_services": {"avg_cpa": 85.0, "avg_roas": 4.0, "avg_ctr": 0.010, "avg_hook_rate": 0.22},
    "education": {"avg_cpa": 65.0, "avg_roas": 3.0, "avg_ctr": 0.014, "avg_hook_rate": 0.28},
    "food_beverage": {"avg_cpa": 28.0, "avg_roas": 4.2, "avg_ctr": 0.025, "avg_hook_rate": 0.40},
    "fashion": {"avg_cpa": 32.0, "avg_roas": 3.8, "avg_ctr": 0.023, "avg_hook_rate": 0.36},
    "home_garden": {"avg_cpa": 42.0, "avg_roas": 3.0, "avg_ctr": 0.017, "avg_hook_rate": 0.30},
    "pets": {"avg_cpa": 35.0, "avg_roas": 3.5, "avg_ctr": 0.020, "avg_hook_rate": 0.35},
    "beauty": {"avg_cpa": 30.0, "avg_roas": 3.8, "avg_ctr": 0.024, "avg_hook_rate": 0.40},
    "cbd_wellness": {"avg_cpa": 55.0, "avg_roas": 2.2, "avg_ctr": 0.013, "avg_hook_rate": 0.28},
    "info_products": {"avg_cpa": 75.0, "avg_roas": 4.5, "avg_ctr": 0.016, "avg_hook_rate": 0.30},
    "agency_default": {"avg_cpa": 45.0, "avg_roas": 3.0, "avg_ctr": 0.018, "avg_hook_rate": 0.32},
}


@router.get("/benchmarks/{industry}")
async def get_industry_benchmarks(industry: str) -> dict:
    """Get industry benchmark averages."""
    benchmarks = INDUSTRY_BENCHMARKS.get(industry)
    if not benchmarks:
        available = list(INDUSTRY_BENCHMARKS.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Industry '{industry}' not found. Available: {available}",
        )
    return {"industry": industry, **benchmarks}


@router.get("/benchmarks")
async def list_all_benchmarks() -> dict:
    """List all available industry benchmarks."""
    return INDUSTRY_BENCHMARKS


# ── Learning Sync ───────────────────────────────────────────────────

@router.post("/sync-learning", status_code=status.HTTP_202_ACCEPTED)
async def sync_learning(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    offer_id: str | None = Query(None),
) -> dict:
    """Trigger the full learning loop from accumulated performance data.

    Runs: skill updates from winners + auto-primer updates.
    """
    win_def = await _get_winning_definition(db, account_id, offer_id)

    # Get recent winners
    winner_stmt = (
        select(PerformanceSnapshot)
        .where(
            PerformanceSnapshot.account_id == account_id,
            PerformanceSnapshot.performance_tier.in_(["winner", "strong"]),
        )
        .order_by(PerformanceSnapshot.date.desc())
        .limit(30)
    )
    result = await db.execute(winner_stmt)
    winners = list(result.scalars().all())

    updates: list[str] = []

    if winners:
        from app.services.intelligence.skill_manager import SkillDomain, skill_manager
        for w in winners[:10]:
            attrs = {"ad_name": w.ad_name, "campaign_name": w.campaign_name}
            perf = {"roas": w.roas or 0, "ctr": w.ctr or 0, "cpa": w.cpa or 0, "tier": w.performance_tier}
            for domain in [SkillDomain.HOOKS, SkillDomain.VISUALS, SkillDomain.COPY, SkillDomain.AUDIENCE]:
                await skill_manager.learn_from_performance(account_id, domain, perf, attrs)
        updates.append(f"Skills updated from {len(winners)} winners")

        if offer_id:
            from app.services.intelligence.auto_primer import auto_update_all_primers
            winner_data: dict[str, Any] = {
                "assets": {
                    w.id: {
                        "roas": w.roas or 0,
                        "ctr": w.ctr or 0,
                        "content": {"hook": w.ad_name or "", "headline": w.ad_name or ""},
                    }
                    for w in winners
                },
            }
            primer_updates = await auto_update_all_primers(account_id, offer_id, winner_data)
            updates.append(f"Primers updated: {len(primer_updates)}")

    return {"status": "completed", "updates": updates, "winners_found": len(winners)}


# ── Helpers ─────────────────────────────────────────────────────────

def _safe_div(a: float | int | None, b: float | int | None, multiplier: float = 1.0) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return (a / b) * multiplier


def _classify_tier(
    metric_value: float | None,
    win_def: WinningDefinition,
    spend: float | None,
    impressions: int | None,
) -> str:
    if not spend or spend < win_def.min_spend_for_evaluation:
        return "untested"
    if not impressions or impressions < win_def.min_impressions_for_evaluation:
        return "untested"
    if metric_value is None:
        return "untested"

    if win_def.primary_metric in ("cpa",):
        # Lower is better for CPA
        if metric_value <= win_def.winner_threshold:
            return "winner"
        if metric_value <= win_def.strong_threshold:
            return "strong"
        if metric_value <= win_def.average_threshold:
            return "average"
        if metric_value <= win_def.weak_threshold:
            return "weak"
        return "loser"
    else:
        # Higher is better (ROAS, CTR, etc.)
        if metric_value >= win_def.winner_threshold:
            return "winner"
        if metric_value >= win_def.strong_threshold:
            return "strong"
        if metric_value >= win_def.average_threshold:
            return "average"
        if metric_value >= win_def.weak_threshold:
            return "weak"
        return "loser"


async def _get_winning_definition(
    db: AsyncSession,
    account_id: str,
    offer_id: str | None = None,
) -> WinningDefinition:
    """Get or create the winning definition for an account."""
    conditions = [WinningDefinition.account_id == account_id]
    if offer_id:
        conditions.append(WinningDefinition.offer_id == offer_id)

    stmt = select(WinningDefinition).where(and_(*conditions)).limit(1)
    result = await db.execute(stmt)
    win_def = result.scalar_one_or_none()

    if not win_def:
        win_def = WinningDefinition(
            id=f"wd_{uuid4().hex[:12]}",
            account_id=account_id,
            offer_id=offer_id,
        )
        db.add(win_def)
        await db.flush()

    return win_def


async def _create_question(
    db: AsyncSession,
    account_id: str,
    data_source: str,
    related_field: str,
    related_value: str,
    question: str,
    question_type: str,
    options: list[str] | None = None,
) -> IngestQuestion:
    q = IngestQuestion(
        id=f"iq_{uuid4().hex[:12]}",
        account_id=account_id,
        data_source=data_source,
        related_field=related_field,
        related_value=related_value,
        question=question,
        question_type=question_type,
        options=options,
    )
    db.add(q)
    return q

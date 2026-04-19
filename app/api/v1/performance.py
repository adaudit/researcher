"""Performance data ingest — schema for Bulk Launcher / Ad Audit.

Defines the exact data shape expected from external ad performance
sources. The system doesn't pull from Meta Ads API directly — it
receives structured performance data and routes it to:
  1. creative_assets (update performance columns)
  2. skill_manager (learn from performance)
  3. auto_primer (update primers from winners)
  4. ad_analyzer (deep analysis of winners/losers)
  5. Hindsight CREATIVE bank (retain performance signals)

POST /v1/performance/ingest — bulk performance data ingest
POST /v1/performance/sync   — sync and trigger full learning loop
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.creative import CreativeAsset
from app.db.session import get_db
from app.services.hindsight.banks import BankType
from app.services.hindsight.memory import retain_observation

router = APIRouter()


# ── Data Schema ─────────────────────────────────────────────────────

class AdPerformanceRecord(BaseModel):
    """Performance data for a single ad creative.

    This is the shape Bulk Launcher / Ad Audit should send.
    All fields optional except ad_id — send what you have.
    """

    # Identity — at least one required to match the creative
    ad_id: str = Field(..., description="External ad ID from the platform")
    platform: str = Field("meta", description="meta | tiktok | google | youtube | linkedin")
    asset_id: str | None = Field(None, description="Our internal creative_asset ID if known")
    ad_name: str | None = None

    # Core metrics
    spend: float | None = None
    impressions: int | None = None
    clicks: int | None = None
    conversions: int | None = None
    revenue: float | None = None

    # Calculated metrics (send if available, otherwise we calculate)
    ctr: float | None = None           # click-through rate
    cpa: float | None = None           # cost per acquisition
    roas: float | None = None          # return on ad spend
    cpc: float | None = None           # cost per click
    cpm: float | None = None           # cost per thousand impressions

    # Video-specific metrics
    hook_rate: float | None = None           # % who watch past 3s
    thumb_stop_ratio: float | None = None    # thumb stop rate
    avg_watch_time_seconds: float | None = None
    video_plays: int | None = None
    video_completions: int | None = None

    # Creative content (for matching and analysis)
    headline: str | None = None
    body_copy: str | None = None
    image_url: str | None = None
    video_url: str | None = None

    # Time range
    date_start: str | None = None      # YYYY-MM-DD
    date_end: str | None = None
    running_days: int | None = None

    # Status
    is_active: bool | None = None
    delivery_status: str | None = None  # active | paused | deleted | completed


class PerformanceIngestRequest(BaseModel):
    """Bulk performance data ingest from Bulk Launcher / Ad Audit."""

    offer_id: str | None = None
    source: str = Field("bulk_launcher", description="bulk_launcher | ad_audit | manual | csv")
    records: list[AdPerformanceRecord]


class PerformanceIngestResponse(BaseModel):
    total_records: int
    matched_assets: int
    new_assets_created: int
    winners_found: int
    losers_found: int
    skill_updates_triggered: int
    primer_updates_triggered: int


class PerformanceSyncRequest(BaseModel):
    """Trigger full learning loop after performance data is ingested."""

    offer_id: str | None = None
    run_ad_analysis: bool = Field(True, description="Run deep ad analysis on winners")
    run_skill_update: bool = Field(True, description="Update skills from performance")
    run_primer_update: bool = Field(True, description="Update primers from winners")
    winner_roas_threshold: float = Field(2.0, description="ROAS threshold for 'winner'")
    loser_roas_threshold: float = Field(0.5, description="ROAS threshold for 'loser'")


# ── Endpoints ───────────────────────────────────────────────────────

@router.post("/ingest", response_model=PerformanceIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_performance_data(
    body: PerformanceIngestRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> PerformanceIngestResponse:
    """Ingest bulk performance data from Bulk Launcher or Ad Audit.

    For each record:
    1. Try to match to an existing creative_asset (by asset_id or ad_id)
    2. Update performance columns on the asset
    3. Calculate derived metrics if missing
    4. Classify performance tier (winner/strong/average/weak/loser)
    5. Retain performance signal to Hindsight CREATIVE bank
    """
    matched = 0
    created = 0
    winners = 0
    losers = 0

    for record in body.records:
        # Calculate derived metrics
        _fill_derived_metrics(record)

        # Determine performance tier
        tier = _classify_performance_tier(record)
        if tier == "winner":
            winners += 1
        elif tier == "loser":
            losers += 1

        # Try to match existing asset
        asset = None
        if record.asset_id:
            stmt = select(CreativeAsset).where(
                CreativeAsset.id == record.asset_id,
                CreativeAsset.account_id == account_id,
            )
            result = await db.execute(stmt)
            asset = result.scalar_one_or_none()

        if not asset:
            # Search by content hash or ad_id in metadata
            stmt = select(CreativeAsset).where(
                CreativeAsset.account_id == account_id,
                CreativeAsset.metadata["ad_id"].as_string() == record.ad_id,
            )
            result = await db.execute(stmt)
            asset = result.scalar_one_or_none()

        if asset:
            # Update existing asset with performance data
            asset.spend = record.spend
            asset.impressions = record.impressions
            asset.clicks = record.clicks
            asset.ctr = record.ctr
            asset.cpa = record.cpa
            asset.roas = record.roas
            asset.hook_rate = record.hook_rate
            asset.thumb_stop_ratio = record.thumb_stop_ratio
            asset.running_days = record.running_days
            asset.performance_tier = tier
            matched += 1
        else:
            # Create new asset from performance data
            from uuid import uuid4
            asset = CreativeAsset(
                id=f"ca_{uuid4().hex[:12]}",
                account_id=account_id,
                offer_id=body.offer_id,
                asset_type="image" if not record.video_url else "video",
                ownership="own",
                source_platform=record.platform,
                headline=record.headline,
                body_copy=record.body_copy,
                spend=record.spend,
                impressions=record.impressions,
                clicks=record.clicks,
                ctr=record.ctr,
                cpa=record.cpa,
                roas=record.roas,
                hook_rate=record.hook_rate,
                thumb_stop_ratio=record.thumb_stop_ratio,
                running_days=record.running_days,
                performance_tier=tier,
                processing_status="pending",
                metadata={"ad_id": record.ad_id, "source": body.source},
            )
            db.add(asset)
            created += 1

        # Retain to Hindsight
        perf_text = (
            f"Performance ({record.ad_id}): "
            f"Tier={tier}, Spend=${record.spend or 0:.2f}, "
            f"CTR={record.ctr or 0:.2%}, CPA=${record.cpa or 0:.2f}, "
            f"ROAS={record.roas or 0:.2f}, "
            f"Hook rate={record.hook_rate or 0:.1%}."
        )
        if record.headline:
            perf_text += f" Headline: {record.headline[:100]}"

        await retain_observation(
            account_id=account_id,
            bank_type=BankType.CREATIVE,
            content=perf_text,
            offer_id=body.offer_id,
            source_type="performance",
            evidence_type="performance_signal",
            confidence_score=0.95,
            extra_metadata={
                "ad_id": record.ad_id,
                "tier": tier,
                "roas": record.roas,
                "spend": record.spend,
            },
        )

    await db.commit()

    return PerformanceIngestResponse(
        total_records=len(body.records),
        matched_assets=matched,
        new_assets_created=created,
        winners_found=winners,
        losers_found=losers,
        skill_updates_triggered=0,  # Triggered via /sync
        primer_updates_triggered=0,
    )


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_performance_learning(
    body: PerformanceSyncRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger the full learning loop after performance data is ingested.

    Runs: ad analysis on winners → skill updates → primer updates.
    This is the core flywheel: performance → learning → better output.
    """
    results: dict[str, Any] = {"triggered": []}

    # Get winners and losers
    winner_stmt = select(CreativeAsset).where(
        CreativeAsset.account_id == account_id,
        CreativeAsset.performance_tier.in_(["winner", "strong"]),
    ).order_by(CreativeAsset.updated_at.desc()).limit(20)

    winner_result = await db.execute(winner_stmt)
    winners = list(winner_result.scalars().all())

    # Trigger skill updates from winners
    if body.run_skill_update and winners:
        from app.services.intelligence.skill_manager import SkillDomain, skill_manager
        for winner in winners[:10]:
            attrs = {
                "hook_type": winner.hook_type,
                "format_type": winner.format_type,
                "visual_style": winner.visual_style,
                "awareness_level": winner.awareness_level,
                "headline": winner.headline,
            }
            perf = {
                "roas": winner.roas,
                "ctr": winner.ctr,
                "cpa": winner.cpa,
                "spend": winner.spend,
                "tier": winner.performance_tier,
            }
            for domain in [SkillDomain.HOOKS, SkillDomain.VISUALS, SkillDomain.COPY]:
                await skill_manager.learn_from_performance(
                    account_id, domain, perf, attrs,
                )
        results["triggered"].append(f"skill_updates: {len(winners)} winners processed")

    # Trigger primer updates
    if body.run_primer_update and winners:
        from app.services.intelligence.auto_primer import auto_update_all_primers
        winner_data: dict[str, Any] = {
            "assets": {
                w.id: {
                    "roas": w.roas or 0,
                    "ctr": w.ctr or 0,
                    "cpa": w.cpa or 0,
                    "spend": w.spend or 0,
                    "content": {
                        "body": w.body_copy or "",
                        "hook": (w.headline or "")[:200],
                        "headline": w.headline or "",
                    },
                }
                for w in winners
            },
        }
        if body.offer_id:
            updates = await auto_update_all_primers(
                account_id, body.offer_id, winner_data,
            )
            results["triggered"].append(f"primer_updates: {len(updates)} primers updated")

    return results


# ── Helpers ─────────────────────────────────────────────────────────

def _fill_derived_metrics(record: AdPerformanceRecord) -> None:
    """Calculate derived metrics if not provided."""
    if record.ctr is None and record.clicks and record.impressions:
        record.ctr = record.clicks / max(record.impressions, 1)
    if record.cpa is None and record.spend and record.conversions:
        record.cpa = record.spend / max(record.conversions, 1)
    if record.roas is None and record.revenue and record.spend:
        record.roas = record.revenue / max(record.spend, 0.01)
    if record.cpc is None and record.spend and record.clicks:
        record.cpc = record.spend / max(record.clicks, 1)
    if record.cpm is None and record.spend and record.impressions:
        record.cpm = (record.spend / max(record.impressions, 1)) * 1000


def _classify_performance_tier(record: AdPerformanceRecord) -> str:
    """Classify a record's performance tier."""
    roas = record.roas or 0
    spend = record.spend or 0

    if spend < 10:
        return "untested"
    if roas >= 3.0:
        return "winner"
    if roas >= 2.0:
        return "strong"
    if roas >= 1.0:
        return "average"
    if roas >= 0.5:
        return "weak"
    return "loser"

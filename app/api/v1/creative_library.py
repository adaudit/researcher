"""Creative Library API — ingest, search, categorize, and study creatives.

POST   /v1/creative-library/ingest         — ingest and auto-categorize a creative
GET    /v1/creative-library/assets          — search creative assets by dimensions
GET    /v1/creative-library/swipes          — search swipe file
POST   /v1/creative-library/swipes          — manually add a swipe entry
GET    /v1/creative-library/categories      — list all categorization dimensions
POST   /v1/creative-library/analyze-video   — trigger video analysis pipeline
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.session import get_db
from app.services.intelligence.creative_library import (
    CATEGORIZATION_DIMENSIONS,
    creative_library,
)

router = APIRouter()


class IngestRequest(BaseModel):
    asset_type: str = Field(..., description="video | image | carousel_card | ugc | email_creative")
    ownership: str = Field("own", description="own | competitor | swipe | reference | template")
    headline: str = ""
    body_copy: str = ""
    source_url: str = ""
    source_platform: str = ""
    advertiser_name: str = ""
    offer_id: str | None = None
    performance_data: dict | None = None
    metadata: dict | None = None


class IngestResponse(BaseModel):
    asset_id: str
    format_type: str | None
    visual_style: str | None
    hook_type: str | None
    awareness_level: str | None
    performance_tier: str | None
    auto_categorized: bool = True


class SwipeCreateRequest(BaseModel):
    asset_type: str = "image"
    headline: str = ""
    body_copy: str = ""
    source_url: str = ""
    source_platform: str = ""
    advertiser_name: str = ""
    swipe_source: str = Field("competitor", description="competitor | adjacent_market | organic_viral | template | reference")
    study_notes: str = ""
    offer_id: str | None = None
    industry: str | None = None
    vertical: str | None = None
    tags: list[str] | None = None


class AssetSummary(BaseModel):
    id: str
    asset_type: str
    ownership: str
    headline: str | None
    format_type: str | None
    visual_style: str | None
    hook_type: str | None
    awareness_level: str | None
    performance_tier: str | None
    source_platform: str | None
    advertiser_name: str | None


class SwipeSummary(BaseModel):
    id: str
    swipe_source: str
    format_type: str | None
    hook_type: str | None
    awareness_level: str | None
    study_notes: str | None
    why_it_works: str | None
    what_to_steal: str | None
    industry: str | None


class VideoAnalysisRequest(BaseModel):
    storage_key: str = Field(..., description="S3 key of the video in researcher-media bucket")
    offer_id: str | None = None
    video_uri: str | None = Field(None, description="Direct video URI for Gemini (if not using S3)")


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_creative(
    body: IngestRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest a creative asset, auto-categorize it, and add to the library."""
    asset = await creative_library.ingest_and_categorize(
        db,
        account_id=account_id,
        asset_type=body.asset_type,
        ownership=body.ownership,
        headline=body.headline,
        body_copy=body.body_copy,
        source_url=body.source_url,
        source_platform=body.source_platform,
        advertiser_name=body.advertiser_name,
        offer_id=body.offer_id,
        performance_data=body.performance_data,
        extra_metadata=body.metadata,
    )
    return IngestResponse(
        asset_id=asset.id,
        format_type=asset.format_type,
        visual_style=asset.visual_style,
        hook_type=asset.hook_type,
        awareness_level=asset.awareness_level,
        performance_tier=asset.performance_tier,
    )


@router.get("/assets", response_model=list[AssetSummary])
async def search_assets(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    format_type: str | None = Query(None),
    visual_style: str | None = Query(None),
    hook_type: str | None = Query(None),
    awareness_level: str | None = Query(None),
    performance_tier: str | None = Query(None),
    ownership: str | None = Query(None),
    asset_type: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list[AssetSummary]:
    """Search creative assets by any combination of dimensions."""
    assets = await creative_library.search(
        db, account_id,
        format_type=format_type,
        visual_style=visual_style,
        hook_type=hook_type,
        awareness_level=awareness_level,
        performance_tier=performance_tier,
        ownership=ownership,
        asset_type=asset_type,
        limit=limit,
    )
    return [
        AssetSummary(
            id=a.id,
            asset_type=a.asset_type,
            ownership=a.ownership,
            headline=a.headline,
            format_type=a.format_type,
            visual_style=a.visual_style,
            hook_type=a.hook_type,
            awareness_level=a.awareness_level,
            performance_tier=a.performance_tier,
            source_platform=a.source_platform,
            advertiser_name=a.advertiser_name,
        )
        for a in assets
    ]


@router.get("/swipes", response_model=list[SwipeSummary])
async def search_swipes(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
    swipe_source: str | None = Query(None),
    format_type: str | None = Query(None),
    hook_type: str | None = Query(None),
    awareness_level: str | None = Query(None),
    industry: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list[SwipeSummary]:
    """Search the swipe file by category."""
    swipes = await creative_library.search_swipes(
        db, account_id,
        swipe_source=swipe_source,
        format_type=format_type,
        hook_type=hook_type,
        awareness_level=awareness_level,
        industry=industry,
        limit=limit,
    )
    return [
        SwipeSummary(
            id=s.id,
            swipe_source=s.swipe_source,
            format_type=s.format_type,
            hook_type=s.hook_type,
            awareness_level=s.awareness_level,
            study_notes=s.study_notes,
            why_it_works=s.why_it_works,
            what_to_steal=s.what_to_steal,
            industry=s.industry,
        )
        for s in swipes
    ]


@router.post("/swipes", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def add_swipe(
    body: SwipeCreateRequest,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Manually add a competitor/reference creative to the swipe file."""
    asset = await creative_library.ingest_and_categorize(
        db,
        account_id=account_id,
        asset_type=body.asset_type,
        ownership="swipe" if body.swipe_source != "competitor" else "competitor",
        headline=body.headline,
        body_copy=body.body_copy,
        source_url=body.source_url,
        source_platform=body.source_platform,
        advertiser_name=body.advertiser_name,
        offer_id=body.offer_id,
    )
    return IngestResponse(
        asset_id=asset.id,
        format_type=asset.format_type,
        visual_style=asset.visual_style,
        hook_type=asset.hook_type,
        awareness_level=asset.awareness_level,
        performance_tier=asset.performance_tier,
    )


@router.get("/categories")
async def list_categories() -> dict:
    """List all categorization dimensions and their valid values."""
    return CATEGORIZATION_DIMENSIONS


@router.post("/analyze-video", status_code=status.HTTP_202_ACCEPTED)
async def trigger_video_analysis(
    body: VideoAnalysisRequest,
    account_id: str = Depends(get_current_account_id),
) -> dict:
    """Trigger the full video analysis pipeline.

    The pipeline runs asynchronously: Gemini analysis → timestamp
    validation → ffmpeg clip cutting → S3 upload → manifest creation.
    """
    from app.workers.base import WorkerInput
    from app.workers.video_analysis_pipeline import VideoAnalysisPipelineWorker

    worker = VideoAnalysisPipelineWorker()
    result = await worker.run(WorkerInput(
        account_id=account_id,
        offer_id=body.offer_id,
        params={
            "storage_key": body.storage_key,
            "video_uri": body.video_uri,
        },
    ))

    return {
        "status": "completed" if result.success else "failed",
        "data": result.data,
        "errors": result.errors,
    }

"""POST /v1/offers — create or update an offer."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.core.events import DomainEvent, EventTopic, event_bus
from app.db.models.offer import Offer
from app.db.session import get_db
from app.schemas.offer import OfferCreate, OfferResponse, OfferUpdate
from app.services.hindsight.banks import provision_offer_bank

router = APIRouter()


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: OfferCreate,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Offer:
    offer_id = f"offer_{uuid4().hex[:12]}"

    offer = Offer(
        id=offer_id,
        account_id=account_id,
        **body.model_dump(),
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)

    # Provision Hindsight offer bank
    try:
        bank_id = await provision_offer_bank(account_id, offer_id)
        offer.hindsight_offer_bank_id = bank_id
        await db.commit()
    except Exception:
        pass

    return offer


@router.get("/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Offer:
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id, Offer.account_id == account_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: str,
    body: OfferUpdate,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> Offer:
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id, Offer.account_id == account_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(offer, field, value)

    await db.commit()
    await db.refresh(offer)

    await event_bus.publish(DomainEvent(
        topic=EventTopic.OFFER_UPDATED,
        payload={"offer_id": offer_id},
        account_id=account_id,
        offer_id=offer_id,
    ))

    return offer


@router.get("", response_model=list[OfferResponse])
async def list_offers(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[Offer]:
    result = await db.execute(
        select(Offer).where(Offer.account_id == account_id).order_by(Offer.created_at.desc())
    )
    return list(result.scalars().all())

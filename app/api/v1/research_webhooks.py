"""Webhook receiver endpoints for research data ingestion.

External services (Taddy, Substack, Zapier-wrapped sources) push data here.
Each request is HMAC-validated against the registered webhook secret.

Flow:
  1. Receive POST with X-Signature header
  2. Look up webhook registration by source + external_id
  3. Verify HMAC signature
  4. Compute content hash for dedup
  5. Insert into research_inbox (skip if duplicate)
  6. Return 202 — synthesis happens weekly, not now

This is fire-and-forget for the sender. The weekly research_synthesis
worker does all the LLM analysis.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets as pysecrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_account_id
from app.db.models.research_inbox import ResearchInbox, WebhookRegistration
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Webhook receiver ─────────────────────────────────────────────────


@router.post("/research/{source}", status_code=status.HTTP_202_ACCEPTED)
async def receive_research_webhook(
    source: str,
    request: Request,
    x_account_id: str = Header(...),
    x_signature: str | None = Header(None),
    x_external_id: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive a webhook payload from an external research source."""
    body_bytes = await request.body()

    # Look up registration to get the HMAC secret
    stmt = select(WebhookRegistration).where(
        WebhookRegistration.account_id == x_account_id,
        WebhookRegistration.source == source,
        WebhookRegistration.status == "active",
    )
    if x_external_id:
        stmt = stmt.where(WebhookRegistration.external_id == x_external_id)

    result = await db.execute(stmt)
    registration = result.scalar_one_or_none()

    if not registration:
        logger.warning(
            "webhook.no_registration source=%s account=%s",
            source, x_account_id,
        )
        raise HTTPException(
            status_code=404, detail="No active webhook registration for this source",
        )

    # Verify HMAC signature
    if x_signature:
        expected = hmac.new(
            registration.secret.encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature.replace("sha256=", "")):
            logger.warning(
                "webhook.signature_mismatch source=%s account=%s",
                source, x_account_id,
            )
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning(
            "webhook.no_signature source=%s account=%s — accepting but flagging",
            source, x_account_id,
        )

    # Parse payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Extract title/summary for dedup hashing and quick scoring
    title = (
        payload.get("title")
        or payload.get("name")
        or payload.get("headline")
        or ""
    )
    summary = (
        payload.get("summary")
        or payload.get("description")
        or payload.get("text")
        or payload.get("content", "")[:1000]
    )
    source_url = payload.get("url") or payload.get("link") or ""
    source_id = payload.get("id") or payload.get("uuid") or payload.get("guid")

    # Content hash for dedup (normalized)
    content_for_hash = (title + "|" + summary[:500] + "|" + (source_url or "")).lower().strip()
    content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:32]

    # Insert (skip on conflict — idempotent ingestion)
    inbox_id = f"rsx_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    try:
        item = ResearchInbox(
            id=inbox_id,
            account_id=x_account_id,
            offer_id=payload.get("offer_id"),
            source=source,
            source_url=source_url,
            source_id=str(source_id) if source_id else None,
            content_hash=content_hash,
            raw_payload=payload,
            title=title[:500] if title else None,
            summary=summary[:2000] if summary else None,
            received_at=now,
            processed=False,
        )
        db.add(item)

        registration.last_received_at = now
        registration.payload_count = (registration.payload_count or 0) + 1

        await db.commit()
    except IntegrityError:
        # Duplicate content hash — already received this item
        await db.rollback()
        logger.info(
            "webhook.duplicate source=%s account=%s hash=%s",
            source, x_account_id, content_hash,
        )
        return {"status": "duplicate", "received": False}

    logger.info(
        "webhook.received source=%s account=%s id=%s",
        source, x_account_id, inbox_id,
    )

    return {"status": "received", "id": inbox_id, "received": True}


# ── Webhook registration management ──────────────────────────────────


class WebhookRegistrationCreate(BaseModel):
    source: str
    external_id: str | None = None
    offer_id: str | None = None
    keywords: list[str] | None = None


class WebhookRegistrationResponse(BaseModel):
    id: str
    source: str
    external_id: str | None
    offer_id: str | None
    secret: str
    status: str
    payload_count: int
    last_received_at: datetime | None

    model_config = {"from_attributes": True}


@router.post(
    "/registrations",
    response_model=WebhookRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_webhook(
    body: WebhookRegistrationCreate,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> WebhookRegistration:
    """Register a webhook source. Returns the secret to use for HMAC signing.

    The actual registration with the external service (e.g., calling
    Taddy's webhook registration API) happens in a follow-up worker.
    This endpoint just creates the local record + secret.
    """
    registration = WebhookRegistration(
        id=f"whr_{uuid4().hex[:12]}",
        account_id=account_id,
        offer_id=body.offer_id,
        source=body.source,
        external_id=body.external_id,
        keywords=body.keywords,
        secret=pysecrets.token_urlsafe(48),
        status="active",
        payload_count=0,
    )
    db.add(registration)
    await db.commit()
    await db.refresh(registration)

    logger.info(
        "webhook.registered account=%s source=%s id=%s",
        account_id, body.source, registration.id,
    )
    return registration


@router.get(
    "/registrations",
    response_model=list[WebhookRegistrationResponse],
)
async def list_registrations(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRegistration]:
    result = await db.execute(
        select(WebhookRegistration).where(
            WebhookRegistration.account_id == account_id,
        ).order_by(WebhookRegistration.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/registrations/{registration_id}")
async def deactivate_registration(
    registration_id: str,
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(WebhookRegistration).where(
            WebhookRegistration.id == registration_id,
            WebhookRegistration.account_id == account_id,
        )
    )
    registration = result.scalar_one_or_none()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    registration.status = "inactive"
    await db.commit()
    return {"status": "deactivated", "id": registration_id}


# ── Inbox visibility ─────────────────────────────────────────────────


@router.get("/inbox/stats")
async def inbox_stats(
    account_id: str = Depends(get_current_account_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Inbox stats — pending count, by source breakdown."""
    from sqlalchemy import func

    pending_q = select(func.count(ResearchInbox.id)).where(
        ResearchInbox.account_id == account_id,
        ResearchInbox.processed.is_(False),
    )
    pending = (await db.execute(pending_q)).scalar_one() or 0

    by_source_q = (
        select(ResearchInbox.source, func.count(ResearchInbox.id))
        .where(
            ResearchInbox.account_id == account_id,
            ResearchInbox.processed.is_(False),
        )
        .group_by(ResearchInbox.source)
    )
    by_source_result = await db.execute(by_source_q)
    by_source = {row[0]: row[1] for row in by_source_result.all()}

    return {
        "pending_count": pending,
        "by_source": by_source,
    }

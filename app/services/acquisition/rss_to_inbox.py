"""RSS poller — converts pull-based sources into webhook-style inbox items.

Sources without native webhooks (Google News RSS, FDA RSS, Federal Register,
arbitrary blog feeds) get polled by this service, which posts each new item
into the same research_inbox table the webhook receivers populate.

Result: the weekly research_synthesis worker doesn't care whether data
arrived via webhook or RSS poll — all sources flow through the same pipe.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

import httpx
from sqlalchemy.exc import IntegrityError

from app.db.models.research_inbox import ResearchInbox
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


# Default RSS sources mapped to logical source names
DEFAULT_RSS_SOURCES = {
    "google_news": "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en",
    "fda_alerts": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
    "federal_register_ftc": (
        "https://www.federalregister.gov/api/v1/documents.rss"
        "?conditions[agencies][]=federal-trade-commission"
    ),
}


async def poll_rss_to_inbox(
    *,
    account_id: str,
    source: str,
    feed_url: str,
    offer_id: str | None = None,
    max_items: int = 50,
) -> dict[str, int]:
    """Poll an RSS feed and post each new item into research_inbox.

    Returns: {fetched: N, ingested: M, duplicates: K}
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning(
            "rss_poller.fetch_failed source=%s url=%s error=%s",
            source, feed_url[:100], exc,
        )
        return {"fetched": 0, "ingested": 0, "duplicates": 0}

    try:
        root = ElementTree.fromstring(resp.text)
    except ElementTree.ParseError:
        logger.warning("rss_poller.parse_failed source=%s", source)
        return {"fetched": 0, "ingested": 0, "duplicates": 0}

    items = root.findall(".//item")[:max_items]
    fetched = len(items)
    ingested = 0
    duplicates = 0

    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            guid = (item.findtext("guid") or link).strip()

            if not (title or description):
                continue

            content_for_hash = (
                title + "|" + description[:500] + "|" + link
            ).lower().strip()
            content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()[:32]

            payload = {
                "title": title,
                "link": link,
                "description": description,
                "published": pub_date,
                "guid": guid,
                "source": source,
            }

            try:
                inbox_item = ResearchInbox(
                    id=f"rsx_{uuid4().hex[:12]}",
                    account_id=account_id,
                    offer_id=offer_id,
                    source=source,
                    source_url=link,
                    source_id=guid[:256] if guid else None,
                    content_hash=content_hash,
                    raw_payload=payload,
                    title=title[:500] if title else None,
                    summary=description[:2000] if description else None,
                    received_at=now,
                    processed=False,
                )
                db.add(inbox_item)
                await db.commit()
                ingested += 1
            except IntegrityError:
                # Already in inbox (duplicate content_hash)
                await db.rollback()
                duplicates += 1
            except Exception as exc:
                await db.rollback()
                logger.debug(
                    "rss_poller.insert_failed source=%s error=%s",
                    source, exc,
                )

    logger.info(
        "rss_poller.complete source=%s account=%s fetched=%d ingested=%d duplicates=%d",
        source, account_id, fetched, ingested, duplicates,
    )

    return {"fetched": fetched, "ingested": ingested, "duplicates": duplicates}


async def poll_default_sources_for_offer(
    account_id: str,
    offer_id: str,
    keywords: list[str],
) -> list[dict[str, Any]]:
    """Poll Google News for each keyword + standing FDA/FTC feeds.

    Designed to run on a daily cron — the resulting inbox items get
    processed by the weekly research_synthesis worker.
    """
    results: list[dict[str, Any]] = []

    for kw in keywords[:5]:
        from urllib.parse import quote_plus
        url = DEFAULT_RSS_SOURCES["google_news"].format(query=quote_plus(kw))
        stats = await poll_rss_to_inbox(
            account_id=account_id,
            source=f"google_news:{kw[:32]}",
            feed_url=url,
            offer_id=offer_id,
        )
        results.append({"keyword": kw, **stats})

    # Standing regulatory feeds (offer-agnostic, but tagged to the offer
    # so the synthesis step can score relevance per-offer)
    for feed_source in ("fda_alerts", "federal_register_ftc"):
        stats = await poll_rss_to_inbox(
            account_id=account_id,
            source=feed_source,
            feed_url=DEFAULT_RSS_SOURCES[feed_source],
            offer_id=offer_id,
            max_items=20,
        )
        results.append({"feed": feed_source, **stats})

    return results

"""Landing page acquisition: fetch rendered HTML, static HTML, screenshots,
and detect embedded video elements.

Step 1-3 of the landing page processing pipeline from the blueprint.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class PageCapture:
    url: str
    html: bytes
    content_hash: str
    title: str | None = None
    text_blocks: list[dict[str, Any]] = field(default_factory=list)
    embedded_videos: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoAsset:
    source_url: str
    embed_type: str  # youtube | vimeo | wistia | html5 | loom | other
    element_html: str
    page_section: str | None = None


async def fetch_page(url: str, *, timeout: float = 30.0) -> PageCapture:
    """Fetch a landing page and extract structural content.

    For MVP this uses httpx for static HTML. Production should use
    Playwright for JS-rendered pages (the dependency is included).
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "ResearcherBot/0.1"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    html_bytes = resp.content
    content_hash = hashlib.sha256(html_bytes).hexdigest()

    soup = BeautifulSoup(html_bytes, "lxml")

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = _extract_meta(soup)
    text_blocks = _extract_text_blocks(soup)
    videos = _detect_embedded_videos(soup, url)

    logger.info(
        "page.fetched url=%s blocks=%d videos=%d",
        url,
        len(text_blocks),
        len(videos),
    )

    return PageCapture(
        url=url,
        html=html_bytes,
        content_hash=content_hash,
        title=title,
        text_blocks=text_blocks,
        embedded_videos=[_video_to_dict(v) for v in videos],
        meta=meta,
    )


def _extract_meta(soup: BeautifulSoup) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property", "")
        content = tag.get("content", "")
        if name and content:
            meta[name] = content
    return meta


def _extract_text_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract visible text blocks with semantic tags."""
    blocks: list[dict[str, Any]] = []
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption"]

    for tag in soup.find_all(block_tags):
        text = tag.get_text(strip=True)
        if text and len(text) > 3:
            blocks.append({
                "tag": tag.name,
                "text": text,
                "parent_id": tag.parent.get("id") if tag.parent else None,
                "parent_class": " ".join(tag.parent.get("class", [])) if tag.parent else None,
            })
    return blocks


def _detect_embedded_videos(soup: BeautifulSoup, page_url: str) -> list[VideoAsset]:
    """Detect embedded video elements and media URLs."""
    videos: list[VideoAsset] = []

    # iframes (YouTube, Vimeo, Wistia, Loom, etc.)
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if not src:
            continue
        embed_type = _classify_embed(src)
        if embed_type:
            videos.append(VideoAsset(
                source_url=src,
                embed_type=embed_type,
                element_html=str(iframe),
                page_section=_nearest_section(iframe),
            ))

    # HTML5 video elements
    for video in soup.find_all("video"):
        source = video.find("source")
        src = video.get("src") or (source.get("src") if source else None) or ""
        if src:
            videos.append(VideoAsset(
                source_url=src,
                embed_type="html5",
                element_html=str(video),
                page_section=_nearest_section(video),
            ))

    return videos


def _classify_embed(src: str) -> str | None:
    domain = urlparse(src).hostname or ""
    if "youtube" in domain or "youtu.be" in domain:
        return "youtube"
    if "vimeo" in domain:
        return "vimeo"
    if "wistia" in domain:
        return "wistia"
    if "loom" in domain:
        return "loom"
    if any(ext in src for ext in [".mp4", ".webm", ".m3u8"]):
        return "html5"
    return "other"


def _nearest_section(element) -> str | None:
    """Walk up the DOM to find the nearest section-level container."""
    for parent in element.parents:
        if parent.name in ("section", "article", "div"):
            section_id = parent.get("id")
            if section_id:
                return section_id
            classes = parent.get("class", [])
            if classes:
                return " ".join(classes)
    return None


def _video_to_dict(v: VideoAsset) -> dict[str, Any]:
    return {
        "source_url": v.source_url,
        "embed_type": v.embed_type,
        "element_html": v.element_html,
        "page_section": v.page_section,
    }

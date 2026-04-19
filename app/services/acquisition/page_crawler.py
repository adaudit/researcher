"""Landing page acquisition with Playwright for JS-rendered pages.

Supports both static (httpx) and dynamic (Playwright) rendering.
Dynamic rendering captures JS-generated content, lazy-loaded images,
and interactive elements that static HTML misses.

Pipeline steps 1-3:
  1. Fetch rendered HTML (Playwright) and static HTML (httpx fallback)
  2. Parse visible content and DOM blocks
  3. Detect embedded video elements and media URLs
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
    screenshot: bytes | None = None
    render_mode: str = "static"  # static | playwright


@dataclass
class VideoAsset:
    source_url: str
    embed_type: str  # youtube | vimeo | wistia | html5 | loom | other
    element_html: str
    page_section: str | None = None


async def fetch_page(
    url: str,
    *,
    timeout: float = 30.0,
    use_playwright: bool = True,
    take_screenshot: bool = True,
    wait_for_idle: bool = True,
) -> PageCapture:
    """Fetch a landing page with JS rendering via Playwright.

    Falls back to static httpx fetch if Playwright is unavailable.
    """
    if use_playwright:
        try:
            return await _fetch_with_playwright(
                url,
                timeout=timeout,
                take_screenshot=take_screenshot,
                wait_for_idle=wait_for_idle,
            )
        except Exception as exc:
            logger.warning("page.playwright_fallback url=%s error=%s", url, exc)

    return await _fetch_static(url, timeout=timeout)


async def _fetch_with_playwright(
    url: str,
    *,
    timeout: float = 30.0,
    take_screenshot: bool = True,
    wait_for_idle: bool = True,
) -> PageCapture:
    """Full JS-rendered page capture using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = await context.new_page()

        # Navigate and wait for network idle to catch lazy-loaded content
        await page.goto(url, timeout=int(timeout * 1000))
        if wait_for_idle:
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # Some pages never reach idle — continue anyway

        # Scroll to trigger lazy loading
        await _scroll_page(page)

        # Get rendered HTML
        html_content = await page.content()
        html_bytes = html_content.encode("utf-8")
        content_hash = hashlib.sha256(html_bytes).hexdigest()

        # Take screenshot
        screenshot = None
        if take_screenshot:
            screenshot = await page.screenshot(full_page=True, type="png")

        await browser.close()

    soup = BeautifulSoup(html_bytes, "lxml")

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = _extract_meta(soup)
    text_blocks = _extract_text_blocks(soup)
    videos = _detect_embedded_videos(soup, url)

    logger.info(
        "page.fetched url=%s mode=playwright blocks=%d videos=%d",
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
        screenshot=screenshot,
        render_mode="playwright",
    )


async def _scroll_page(page) -> None:
    """Scroll the page to trigger lazy-loaded content."""
    try:
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = 900
        current = 0

        while current < total_height:
            current += viewport_height
            await page.evaluate(f"window.scrollTo(0, {current})")
            await page.wait_for_timeout(300)

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)
    except Exception:
        pass


async def _fetch_static(url: str, *, timeout: float = 30.0) -> PageCapture:
    """Fallback static HTML fetch using httpx."""
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
        "page.fetched url=%s mode=static blocks=%d videos=%d",
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
        render_mode="static",
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
    """Extract visible text blocks with semantic tags and structural context."""
    blocks: list[dict[str, Any]] = []
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote",
                  "figcaption", "span", "a", "button", "label"]

    for tag in soup.find_all(block_tags):
        text = tag.get_text(strip=True)
        if text and len(text) > 3:
            # Skip duplicate text from nested elements
            if blocks and blocks[-1].get("text") == text:
                continue

            blocks.append({
                "tag": tag.name,
                "text": text,
                "parent_id": tag.parent.get("id") if tag.parent else None,
                "parent_class": " ".join(tag.parent.get("class", [])) if tag.parent else None,
                "href": tag.get("href") if tag.name == "a" else None,
            })
    return blocks


def _detect_embedded_videos(soup: BeautifulSoup, page_url: str) -> list[VideoAsset]:
    """Detect embedded video elements and media URLs."""
    videos: list[VideoAsset] = []
    seen_urls: set[str] = set()

    # iframes (YouTube, Vimeo, Wistia, Loom, etc.)
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src", "")
        if not src or src in seen_urls:
            continue
        embed_type = _classify_embed(src)
        if embed_type:
            seen_urls.add(src)
            videos.append(VideoAsset(
                source_url=src,
                embed_type=embed_type,
                element_html=str(iframe)[:500],
                page_section=_nearest_section(iframe),
            ))

    # HTML5 video elements
    for video in soup.find_all("video"):
        source = video.find("source")
        src = video.get("src") or (source.get("src") if source else None) or ""
        if src and src not in seen_urls:
            seen_urls.add(src)
            videos.append(VideoAsset(
                source_url=src,
                embed_type="html5",
                element_html=str(video)[:500],
                page_section=_nearest_section(video),
            ))

    # Wistia popover embeds (script-based)
    for script in soup.find_all("script", src=True):
        src = script.get("src", "")
        if "wistia" in src and src not in seen_urls:
            seen_urls.add(src)
            videos.append(VideoAsset(
                source_url=src,
                embed_type="wistia",
                element_html=str(script)[:500],
                page_section=_nearest_section(script),
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
    if "vidyard" in domain:
        return "vidyard"
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

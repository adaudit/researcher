"""Scrapling-powered web scraper — anti-bot crawling, forums, competitor monitoring.

Augments the existing Playwright-only page_crawler.py with Scrapling's
adaptive element tracking, stealth fetchers, and spider framework for:
- Anti-bot bypass (Cloudflare Turnstile, TLS fingerprint impersonation)
- Forum thread extraction with parent/reply structure
- Competitor page monitoring with change detection
- Web search discovery

Falls back to httpx for simple pages, uses StealthyFetcher for protected
sites, and DynamicFetcher for JS-heavy pages.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Standardized result from any crawl operation."""

    url: str
    html: str
    text_content: str
    title: str | None = None
    content_hash: str = ""
    render_mode: str = "static"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForumPost:
    """Single post in a forum thread."""

    author: str
    content: str
    timestamp: str | None = None
    is_op: bool = False
    parent_id: str | None = None
    post_id: str | None = None
    likes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForumThread:
    """Complete forum thread with parent/reply structure."""

    url: str
    title: str
    posts: list[ForumPost] = field(default_factory=list)
    forum_name: str | None = None
    category: str | None = None
    total_replies: int = 0


@dataclass
class SearchResult:
    """Single search result from web search."""

    url: str
    title: str
    snippet: str
    position: int = 0
    source: str = ""


@dataclass
class ChangeResult:
    """Result of comparing current page to previous state."""

    url: str
    changed: bool
    current_hash: str
    previous_hash: str | None = None
    changes_summary: str | None = None
    new_sections: list[str] = field(default_factory=list)
    removed_sections: list[str] = field(default_factory=list)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class WebScraperService:
    """Scrapling-powered web acquisition with anti-bot bypass.

    Three fetcher tiers:
      1. Fetcher (httpx) — fast, no JS, for simple pages
      2. StealthyFetcher — headless browser with anti-detection
      3. DynamicFetcher — full Playwright for JS-heavy pages

    Usage:
        scraper = WebScraperService()
        result = await scraper.crawl_url("https://example.com", stealth=True)
        thread = await scraper.crawl_forum_thread("https://reddit.com/r/...")
        changes = await scraper.monitor_competitor_page(url, previous_hash)
    """

    def __init__(self) -> None:
        self._fetcher = None
        self._stealthy = None
        self._dynamic = None

    def _get_fetcher(self):
        """Lazy-init the basic Scrapling Fetcher."""
        if self._fetcher is None:
            try:
                from scrapling.fetchers import Fetcher
                self._fetcher = Fetcher(auto_match=True)
            except ImportError:
                logger.warning("scrapling not installed, falling back to httpx")
                self._fetcher = None
        return self._fetcher

    def _get_stealthy(self):
        """Lazy-init the StealthyFetcher for anti-bot bypass."""
        if self._stealthy is None:
            try:
                from scrapling.fetchers import StealthyFetcher
                self._stealthy = StealthyFetcher(auto_match=True)
            except ImportError:
                logger.warning("scrapling[fetchers] not installed")
                self._stealthy = None
        return self._stealthy

    def _get_dynamic(self):
        """Lazy-init the DynamicFetcher for full JS rendering."""
        if self._dynamic is None:
            try:
                from scrapling.fetchers import DynamicFetcher
                self._dynamic = DynamicFetcher(auto_match=True)
            except ImportError:
                logger.warning("scrapling[fetchers] not installed")
                self._dynamic = None
        return self._dynamic

    async def crawl_url(
        self,
        url: str,
        *,
        stealth: bool = False,
        dynamic: bool = False,
        impersonate: str = "chrome",
    ) -> CrawlResult:
        """Crawl a URL with appropriate fetcher tier.

        Args:
            url: Target URL.
            stealth: Use StealthyFetcher for anti-bot bypass.
            dynamic: Use DynamicFetcher for full JS rendering.
            impersonate: Browser to impersonate (default: chrome).
        """
        logger.info("web_scraper.crawl url=%s stealth=%s dynamic=%s", url, stealth, dynamic)

        if dynamic:
            fetcher = self._get_dynamic()
        elif stealth:
            fetcher = self._get_stealthy()
        else:
            fetcher = self._get_fetcher()

        if fetcher is None:
            # Fallback to httpx if scrapling not available
            return await self._httpx_fallback(url)

        try:
            page = fetcher.get(url, stealthy_headers=True)
            html = page.html_content if hasattr(page, "html_content") else str(page)
            text = page.get_all_text() if hasattr(page, "get_all_text") else ""
            title_el = page.css("title")
            title = title_el[0].text() if title_el else None

            content_hash = _hash_content(text or html)

            return CrawlResult(
                url=url,
                html=html,
                text_content=text,
                title=title,
                content_hash=content_hash,
                render_mode="stealthy" if stealth else "dynamic" if dynamic else "static",
            )
        except Exception as exc:
            logger.warning("web_scraper.crawl_failed url=%s error=%s, falling back", url, exc)
            return await self._httpx_fallback(url)

    async def _httpx_fallback(self, url: str) -> CrawlResult:
        """Simple httpx GET as last-resort fallback."""
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            title = soup.title.string if soup.title else None

        return CrawlResult(
            url=url,
            html=html,
            text_content=text,
            title=title,
            content_hash=_hash_content(text),
            render_mode="httpx_fallback",
        )

    async def crawl_forum_thread(self, url: str) -> ForumThread:
        """Crawl a forum thread and extract structured posts.

        Handles common forum structures: Reddit threads, health forums,
        product forums, public Facebook groups. Uses CSS selectors with
        Scrapling's adaptive element tracking to survive redesigns.
        """
        logger.info("web_scraper.forum_thread url=%s", url)

        result = await self.crawl_url(url, stealth=True)
        posts: list[ForumPost] = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.html, "lxml")

            # Heuristic: try common forum structures
            # Reddit-style
            comment_divs = soup.select("[data-testid='comment'], .comment, .Comment")
            if comment_divs:
                for i, div in enumerate(comment_divs):
                    author_el = div.select_one("[data-testid='comment_author_link'], .author, .Comment__author")
                    content_el = div.select_one("[data-testid='comment'], .md, .Comment__body, .RichTextJSON-root")
                    posts.append(ForumPost(
                        author=author_el.get_text(strip=True) if author_el else "anonymous",
                        content=content_el.get_text(separator="\n", strip=True) if content_el else div.get_text(separator="\n", strip=True),
                        is_op=(i == 0),
                        post_id=div.get("id") or str(i),
                    ))
            else:
                # Generic forum — look for post/reply containers
                for selector in [".post", ".reply", ".message", ".forum-post", "article", ".thread-reply"]:
                    elements = soup.select(selector)
                    if len(elements) >= 2:
                        for i, el in enumerate(elements):
                            author_el = el.select_one(".author, .username, .poster-name, .user-name")
                            content_el = el.select_one(".post-content, .message-body, .post-body, .content")
                            posts.append(ForumPost(
                                author=author_el.get_text(strip=True) if author_el else "anonymous",
                                content=content_el.get_text(separator="\n", strip=True) if content_el else el.get_text(separator="\n", strip=True),
                                is_op=(i == 0),
                                post_id=el.get("id") or str(i),
                            ))
                        break

            # If no structured posts found, fall back to text blocks
            if not posts and result.text_content:
                posts.append(ForumPost(
                    author="unknown",
                    content=result.text_content[:5000],
                    is_op=True,
                ))

        except Exception as exc:
            logger.warning("web_scraper.forum_parse_failed url=%s error=%s", url, exc)
            if result.text_content:
                posts.append(ForumPost(
                    author="unknown",
                    content=result.text_content[:5000],
                    is_op=True,
                ))

        return ForumThread(
            url=url,
            title=result.title or "",
            posts=posts,
            total_replies=max(len(posts) - 1, 0),
        )

    async def monitor_competitor_page(
        self,
        url: str,
        previous_hash: str | None = None,
    ) -> ChangeResult:
        """Crawl a page and compare against previous state.

        Used for detecting competitor landing page changes: new headlines,
        modified proof sections, changed CTAs, pricing updates.
        """
        logger.info("web_scraper.monitor url=%s prev_hash=%s", url, previous_hash)

        result = await self.crawl_url(url, stealth=True)
        current_hash = result.content_hash
        changed = previous_hash is not None and current_hash != previous_hash

        changes_summary = None
        new_sections: list[str] = []
        removed_sections: list[str] = []

        if changed:
            changes_summary = f"Content hash changed from {previous_hash} to {current_hash}"
            # Detailed diff analysis would be done by the competitor_monitor worker
            # with LLM intelligence — we just detect the change here

        return ChangeResult(
            url=url,
            changed=changed,
            current_hash=current_hash,
            previous_hash=previous_hash,
            changes_summary=changes_summary,
            new_sections=new_sections,
            removed_sections=removed_sections,
        )

    async def discover_forum_threads(
        self,
        base_url: str,
        *,
        query: str | None = None,
        max_threads: int = 20,
    ) -> list[str]:
        """Discover forum thread URLs from a forum index page.

        Crawls the base URL (e.g., forum homepage or search results)
        and extracts links to individual threads.
        """
        logger.info("web_scraper.discover_threads base=%s query=%s", base_url, query)

        target_url = base_url
        if query:
            # Many forums use ?q= or ?search= patterns
            sep = "&" if "?" in base_url else "?"
            target_url = f"{base_url}{sep}q={query}"

        result = await self.crawl_url(target_url, stealth=True)

        urls: list[str] = []
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin

            soup = BeautifulSoup(result.html, "lxml")

            # Look for thread links using common patterns
            for selector in [
                "a.thread-title", "a.topic-title", "a.post-link",
                ".thread a", ".topic a", ".discussion a",
                "h3 a", "h2 a",  # generic heading links
            ]:
                links = soup.select(selector)
                if links:
                    for link in links[:max_threads]:
                        href = link.get("href")
                        if href:
                            full_url = urljoin(base_url, href)
                            if full_url not in urls:
                                urls.append(full_url)
                    if urls:
                        break

            # Fallback: find any links that look like threads
            if not urls:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full = urljoin(base_url, href)
                    if any(pattern in full for pattern in ["/thread/", "/topic/", "/discussion/", "/t/", "/p/"]):
                        if full not in urls:
                            urls.append(full)
                    if len(urls) >= max_threads:
                        break

        except Exception as exc:
            logger.warning("web_scraper.discover_failed base=%s error=%s", base_url, exc)

        return urls[:max_threads]


# Module-level singleton
web_scraper = WebScraperService()

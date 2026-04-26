"""Browser-harness connector — agent-driven interactive browsing.

Wraps the browser-use/browser-harness library for tasks Scrapling can't handle:
  - Interactive browsing (filter dropdowns, click "load more", scroll feeds)
  - Unknown site structures (LLM writes extraction logic on the fly)
  - Landing page captures (full-page screenshot + DOM snapshot)
  - Complex JS-heavy pages (pricing, dynamic checkout flows)

Used as fallback by the research agent when Scrapling and the platform
APIs can't extract what's needed.

Usage:
    from app.services.acquisition.connectors.browser_agent import browser_agent

    result = await browser_agent.navigate_and_extract(
        url="https://competitor.com/pricing",
        goal="Extract all pricing tiers, included features, and any guarantees",
    )
    # result.extracted_data → structured output
    # result.screenshot_url → S3 URL for the captured screenshot
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BrowserResult:
    url: str
    success: bool
    extracted_data: dict[str, Any] = field(default_factory=dict)
    screenshot_bytes: bytes | None = None
    dom_snapshot: str | None = None
    error: str | None = None
    actions_taken: list[str] = field(default_factory=list)


class BrowserAgent:
    """Browser-harness wrapper for agent-driven interactive browsing.

    Falls back to Scrapling DynamicFetcher if browser-harness is not installed,
    with a logged note that capabilities are degraded.
    """

    def __init__(self) -> None:
        self._harness = None
        self._initialized = False

    def _get_harness(self):
        if self._initialized:
            return self._harness

        try:
            from browser_harness import BrowserHarness
            self._harness = BrowserHarness()
            logger.info("browser_agent.harness_ready")
        except ImportError:
            logger.info(
                "browser_agent.harness_not_installed — will fall back to Scrapling DynamicFetcher",
            )
            self._harness = None

        self._initialized = True
        return self._harness

    async def navigate_and_extract(
        self,
        url: str,
        goal: str,
        *,
        capture_screenshot: bool = True,
        max_actions: int = 20,
    ) -> BrowserResult:
        """Navigate to a URL and use an LLM agent to extract data per the goal.

        The agent decides which buttons to click, dropdowns to expand,
        and "load more" actions to take to surface the requested data.
        """
        harness = self._get_harness()

        if harness is None:
            return await self._scrapling_fallback(url, goal, capture_screenshot)

        try:
            session = await harness.create_session()
            await session.goto(url)

            extracted = await session.extract(
                goal=goal,
                max_steps=max_actions,
            )

            screenshot = None
            if capture_screenshot:
                screenshot = await session.screenshot(full_page=True)

            dom = await session.dom_snapshot() if hasattr(session, "dom_snapshot") else None
            actions = (
                session.action_log
                if hasattr(session, "action_log") and isinstance(session.action_log, list)
                else []
            )

            await session.close()

            return BrowserResult(
                url=url,
                success=True,
                extracted_data=extracted if isinstance(extracted, dict) else {"data": extracted},
                screenshot_bytes=screenshot,
                dom_snapshot=dom,
                actions_taken=actions,
            )
        except Exception as exc:
            logger.warning("browser_agent.navigate_failed url=%s error=%s", url, exc)
            return BrowserResult(
                url=url, success=False, error=str(exc),
            )

    async def screenshot(
        self,
        url: str,
        *,
        full_page: bool = True,
    ) -> BrowserResult:
        """Capture a screenshot of a URL (no extraction)."""
        harness = self._get_harness()

        if harness is None:
            return await self._scrapling_fallback(url, "Capture screenshot", True)

        try:
            session = await harness.create_session()
            await session.goto(url)
            screenshot = await session.screenshot(full_page=full_page)
            await session.close()

            return BrowserResult(
                url=url,
                success=True,
                screenshot_bytes=screenshot,
            )
        except Exception as exc:
            logger.warning("browser_agent.screenshot_failed url=%s error=%s", url, exc)
            return BrowserResult(url=url, success=False, error=str(exc))

    async def interact(
        self,
        url: str,
        instructions: str,
    ) -> BrowserResult:
        """Execute interactive instructions (e.g., 'fill form, click submit, capture results')."""
        harness = self._get_harness()

        if harness is None:
            return await self._scrapling_fallback(url, instructions, True)

        try:
            session = await harness.create_session()
            await session.goto(url)
            result = await session.act(instructions)
            screenshot = await session.screenshot(full_page=True)
            actions = (
                session.action_log
                if hasattr(session, "action_log") and isinstance(session.action_log, list)
                else []
            )
            await session.close()

            return BrowserResult(
                url=url,
                success=True,
                extracted_data={"result": result},
                screenshot_bytes=screenshot,
                actions_taken=actions,
            )
        except Exception as exc:
            logger.warning("browser_agent.interact_failed url=%s error=%s", url, exc)
            return BrowserResult(url=url, success=False, error=str(exc))

    async def _scrapling_fallback(
        self,
        url: str,
        goal: str,
        capture_screenshot: bool,
    ) -> BrowserResult:
        """Fallback to Scrapling DynamicFetcher when browser-harness is unavailable."""
        try:
            from app.services.acquisition.connectors.web_scraper import web_scraper
            crawl = await web_scraper.crawl_url(url, dynamic=True)

            return BrowserResult(
                url=url,
                success=bool(crawl.html),
                extracted_data={
                    "html": crawl.html[:50000],
                    "text": crawl.text_content[:20000],
                    "title": crawl.title,
                    "fallback_note": "browser-harness unavailable — used Scrapling DynamicFetcher",
                },
                dom_snapshot=crawl.html[:50000],
            )
        except Exception as exc:
            logger.warning("browser_agent.scrapling_fallback_failed url=%s error=%s", url, exc)
            return BrowserResult(url=url, success=False, error=str(exc))


browser_agent = BrowserAgent()

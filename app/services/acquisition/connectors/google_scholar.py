"""Google Scholar search via SerpAPI (free tier: 250/month).

Falls back to Scrapling if SerpAPI key is not configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScholarResult:
    title: str
    snippet: str
    url: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    citations: int = 0
    pdf_url: str | None = None


class GoogleScholarClient:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None and settings.SERPAPI_KEY:
            try:
                import serpapi
                self._client = serpapi.Client(api_key=settings.SERPAPI_KEY)
            except ImportError:
                logger.warning("serpapi package not installed — Scholar search unavailable")
        return self._client

    async def search_papers(
        self,
        query: str,
        *,
        num: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[ScholarResult]:
        client = self._get_client()
        if not client:
            return await self._fallback_search(query, num)

        params: dict[str, Any] = {
            "engine": "google_scholar",
            "q": query,
            "num": num,
        }
        if year_from:
            params["as_ylo"] = year_from
        if year_to:
            params["as_yhi"] = year_to

        try:
            raw = client.search(params)
            results: list[ScholarResult] = []
            for r in raw.get("organic_results", []):
                pub_info = r.get("publication_info", {})
                authors = []
                if isinstance(pub_info.get("authors"), list):
                    authors = [
                        a.get("name", "") for a in pub_info["authors"]
                    ]

                results.append(ScholarResult(
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    url=r.get("link", ""),
                    authors=authors,
                    year=_extract_year(r),
                    journal=pub_info.get("journal", pub_info.get("summary", "")),
                    citations=(
                        r.get("inline_links", {})
                        .get("cited_by", {})
                        .get("total", 0)
                    ),
                    pdf_url=_find_pdf(r),
                ))
            logger.info(
                "scholar.search query=%s results=%d", query[:50], len(results),
            )
            return results
        except Exception as exc:
            logger.warning("scholar.search_failed query=%s error=%s", query[:50], exc)
            return await self._fallback_search(query, num)

    async def _fallback_search(
        self, query: str, num: int,
    ) -> list[ScholarResult]:
        """Scrapling fallback for basic Scholar scraping."""
        try:
            from app.services.acquisition.connectors.web_scraper import web_scraper
            from urllib.parse import quote_plus

            url = f"https://scholar.google.com/scholar?q={quote_plus(query)}&num={num}"
            result = await web_scraper.crawl_url(url, stealth=True)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.html, "lxml")
            results: list[ScholarResult] = []

            for div in soup.select(".gs_ri")[:num]:
                title_el = div.select_one(".gs_rt a")
                snippet_el = div.select_one(".gs_rs")
                results.append(ScholarResult(
                    title=title_el.get_text() if title_el else "",
                    snippet=snippet_el.get_text() if snippet_el else "",
                    url=title_el.get("href", "") if title_el else "",
                ))

            logger.info(
                "scholar.fallback_search query=%s results=%d",
                query[:50], len(results),
            )
            return results
        except Exception as exc:
            logger.debug("scholar.fallback_failed query=%s error=%s", query[:50], exc)
            return []


def _extract_year(result: dict) -> int | None:
    pub_info = result.get("publication_info", {})
    summary = pub_info.get("summary", "")
    import re
    match = re.search(r"\b(19|20)\d{2}\b", summary)
    return int(match.group()) if match else None


def _find_pdf(result: dict) -> str | None:
    for resource in result.get("resources", []):
        if resource.get("file_format") == "PDF":
            return resource.get("link")
    return None


scholar_client = GoogleScholarClient()

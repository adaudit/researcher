"""External research acquisition services.

Handles fetching from:
  - NCBI / PubMed API for health/science evidence
  - News APIs for market signals
  - Generic web research
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    source: str  # pubmed | news | web
    title: str
    summary: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


async def search_pubmed(
    query: str,
    *,
    max_results: int = 10,
) -> list[ResearchResult]:
    """Search PubMed via NCBI E-Utilities API.

    Ref: https://www.ncbi.nlm.nih.gov/home/develop/api/
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    if settings.NCBI_API_KEY:
        params["api_key"] = settings.NCBI_API_KEY

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: search for IDs
        search_resp = await client.get(f"{base_url}/esearch.fcgi", params=params)
        search_resp.raise_for_status()
        search_data = search_resp.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return []

        # Step 2: fetch summaries
        summary_params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json",
        }
        if settings.NCBI_API_KEY:
            summary_params["api_key"] = settings.NCBI_API_KEY

        summary_resp = await client.get(f"{base_url}/esummary.fcgi", params=summary_params)
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()

    results: list[ResearchResult] = []
    for pmid in id_list:
        doc = summary_data.get("result", {}).get(pmid, {})
        if not doc or pmid == "uids":
            continue
        results.append(ResearchResult(
            source="pubmed",
            title=doc.get("title", ""),
            summary=doc.get("sorttitle", doc.get("title", "")),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            metadata={
                "pmid": pmid,
                "pub_date": doc.get("pubdate", ""),
                "source_journal": doc.get("source", ""),
                "authors": [a.get("name", "") for a in doc.get("authors", [])],
            },
        ))

    logger.info("research.pubmed query=%s results=%d", query[:60], len(results))
    return results


async def search_news(
    query: str,
    *,
    max_results: int = 10,
) -> list[ResearchResult]:
    """Placeholder for news API integration.

    In production, integrate with NewsAPI, Google News API, or a similar
    service. For now, returns an empty list so the worker pipeline
    remains functional.
    """
    logger.info("research.news query=%s (placeholder)", query[:60])
    return []


async def fetch_web_page_text(url: str) -> str:
    """Fetch a web page and extract readable text."""
    from bs4 import BeautifulSoup

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": "ResearcherBot/0.1"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    return soup.get_text(separator="\n", strip=True)

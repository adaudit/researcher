"""Regulatory search — FDA (openFDA API) + FTC (Federal Register).

Both are free, no API key required.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RegulatoryClient:
    """Free regulatory search across FDA and FTC."""

    async def search(
        self,
        query: str,
        *,
        source: str = "fda_api",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if source == "fda_api":
            return await self._search_fda(query, limit)
        elif source == "ftc_api":
            return await self._search_ftc(query, limit)
        return []

    async def _search_fda(
        self, query: str, limit: int,
    ) -> list[dict[str, Any]]:
        """Search openFDA for enforcement actions and warnings."""
        from urllib.parse import quote_plus

        url = (
            f"https://api.fda.gov/drug/enforcement.json?"
            f"search={quote_plus(query)}&limit={limit}"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                data = resp.json()

            results: list[dict[str, Any]] = []
            for r in data.get("results", []):
                results.append({
                    "type": "fda_enforcement",
                    "product": r.get("product_description", "")[:200],
                    "reason": r.get("reason_for_recall", "")[:200],
                    "status": r.get("status", ""),
                    "date": r.get("recall_initiation_date", ""),
                    "classification": r.get("classification", ""),
                })
            logger.info("regulatory.fda query=%s results=%d", query[:50], len(results))
            return results
        except Exception as exc:
            logger.debug("regulatory.fda_failed query=%s error=%s", query[:50], exc)
            return []

    async def _search_ftc(
        self, query: str, limit: int,
    ) -> list[dict[str, Any]]:
        """Search Federal Register for FTC enforcement actions."""
        from urllib.parse import quote_plus

        url = (
            f"https://www.federalregister.gov/api/v1/documents.json?"
            f"conditions[term]={quote_plus(query)}"
            f"&conditions[agencies][]=federal-trade-commission"
            f"&per_page={limit}&order=newest"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            results: list[dict[str, Any]] = []
            for r in data.get("results", []):
                results.append({
                    "type": "ftc_action",
                    "title": r.get("title", ""),
                    "abstract": r.get("abstract", "")[:300],
                    "url": r.get("html_url", ""),
                    "date": r.get("publication_date", ""),
                    "document_type": r.get("type", ""),
                })
            logger.info("regulatory.ftc query=%s results=%d", query[:50], len(results))
            return results
        except Exception as exc:
            logger.debug("regulatory.ftc_failed query=%s error=%s", query[:50], exc)
            return []


regulatory_client = RegulatoryClient()

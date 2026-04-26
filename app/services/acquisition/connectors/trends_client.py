"""Google Trends via pytrends (free, no API key)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TrendsClient:
    """Google Trends search — free via pytrends."""

    async def interest_over_time(
        self,
        keyword: str,
        *,
        timeframe: str = "today 3-m",
        geo: str = "US",
    ) -> list[dict[str, Any]]:
        """Get search interest over time for a keyword."""
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()

            if df.empty:
                return []

            results: list[dict[str, Any]] = []
            for date, row in df.iterrows():
                results.append({
                    "date": str(date.date()),
                    "interest": int(row[keyword]),
                    "keyword": keyword,
                    "type": "trend_interest",
                })
            logger.info("trends.interest query=%s points=%d", keyword, len(results))
            return results
        except ImportError:
            logger.debug("trends.pytrends_not_installed")
            return []
        except Exception as exc:
            logger.debug("trends.interest_failed query=%s error=%s", keyword, exc)
            return []

    async def related_queries(
        self,
        keyword: str,
        *,
        geo: str = "US",
    ) -> list[dict[str, Any]]:
        """Get rising and top related queries."""
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl="en-US", tz=360)
            pytrends.build_payload([keyword], timeframe="today 3-m", geo=geo)
            related = pytrends.related_queries()

            results: list[dict[str, Any]] = []
            for qtype in ("rising", "top"):
                df = related.get(keyword, {}).get(qtype)
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        results.append({
                            "query": row.get("query", ""),
                            "value": int(row.get("value", 0)),
                            "type": qtype,
                            "keyword": keyword,
                        })
            return results
        except ImportError:
            return []
        except Exception as exc:
            logger.debug("trends.related_failed query=%s error=%s", keyword, exc)
            return []


trends_client = TrendsClient()

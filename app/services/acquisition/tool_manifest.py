"""Tool manifest — maps research question types to acquisition endpoints.

The research agent planner decomposes a goal into sub-questions, then uses
this manifest to select the best tool(s) for each question. Priority order:
free first, paid second, browser-harness as universal fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolName(str, Enum):
    # Free APIs
    PUBMED = "pubmed"
    GOOGLE_NEWS_RSS = "google_news_rss"
    GOOGLE_TRENDS = "google_trends"
    FDA_API = "fda_api"
    FTC_API = "ftc_api"
    YOUTUBE_DATA_API = "youtube_data_api"
    PRAW_REDDIT = "praw_reddit"
    # Paid APIs
    SCRAPECREATORS = "scrapecreators"
    SERPAPI_SCHOLAR = "serpapi_scholar"
    TADDY_PODCASTS = "taddy_podcasts"
    # Self-hosted / scraping
    SCRAPLING = "scrapling"
    BROWSER_HARNESS = "browser_harness"
    WHISPER = "whisper"


@dataclass(frozen=True)
class ToolSpec:
    name: ToolName
    description: str
    cost: str
    best_for: str
    output_type: str


TOOL_CATALOG: dict[ToolName, ToolSpec] = {
    ToolName.PUBMED: ToolSpec(
        ToolName.PUBMED,
        "NCBI PubMed search for clinical studies and mechanism evidence",
        "free",
        "mechanism_evidence",
        "paper_results",
    ),
    ToolName.GOOGLE_NEWS_RSS: ToolSpec(
        ToolName.GOOGLE_NEWS_RSS,
        "Google News RSS feeds for breaking news and category coverage",
        "free",
        "cultural_pulse",
        "news_items",
    ),
    ToolName.GOOGLE_TRENDS: ToolSpec(
        ToolName.GOOGLE_TRENDS,
        "Google Trends for search volume trends and rising queries",
        "free",
        "trending_content",
        "trend_data",
    ),
    ToolName.FDA_API: ToolSpec(
        ToolName.FDA_API,
        "openFDA API for drug/supplement warnings and enforcement actions",
        "free",
        "regulatory",
        "enforcement_records",
    ),
    ToolName.FTC_API: ToolSpec(
        ToolName.FTC_API,
        "Federal Register API for FTC advertising enforcement",
        "free",
        "regulatory",
        "enforcement_records",
    ),
    ToolName.YOUTUBE_DATA_API: ToolSpec(
        ToolName.YOUTUBE_DATA_API,
        "YouTube Data API v3 for video search, comments, channels",
        "free",
        "audience_language",
        "video_results",
    ),
    ToolName.PRAW_REDDIT: ToolSpec(
        ToolName.PRAW_REDDIT,
        "Reddit API via PRAW for post/comment search and rising threads",
        "free",
        "audience_language",
        "post_results",
    ),
    ToolName.SCRAPECREATORS: ToolSpec(
        ToolName.SCRAPECREATORS,
        "ScrapCreators API for 27+ platform data (TikTok, IG, Meta ads, etc.)",
        "paid",
        "competitor_ads",
        "platform_data",
    ),
    ToolName.SERPAPI_SCHOLAR: ToolSpec(
        ToolName.SERPAPI_SCHOLAR,
        "Google Scholar search via SerpAPI for academic papers",
        "paid_low",
        "mechanism_evidence",
        "paper_results",
    ),
    ToolName.TADDY_PODCASTS: ToolSpec(
        ToolName.TADDY_PODCASTS,
        "Taddy API for podcast discovery and transcript retrieval",
        "paid_low",
        "expert_commentary",
        "transcript_results",
    ),
    ToolName.SCRAPLING: ToolSpec(
        ToolName.SCRAPLING,
        "Scrapling web scraper for pages, forums, competitor sites",
        "free",
        "competitor_pages",
        "crawl_results",
    ),
    ToolName.BROWSER_HARNESS: ToolSpec(
        ToolName.BROWSER_HARNESS,
        "AI-driven browser for interactive pages and unknown structures",
        "free",
        "competitor_pages",
        "crawl_results",
    ),
    ToolName.WHISPER: ToolSpec(
        ToolName.WHISPER,
        "Whisper speech-to-text for audio/video transcription",
        "free",
        "expert_commentary",
        "transcript_text",
    ),
}


# Question type → tools in priority order (free first, paid second)
TOOL_PRIORITY: dict[str, list[ToolName]] = {
    "audience_language": [
        ToolName.PRAW_REDDIT,
        ToolName.YOUTUBE_DATA_API,
        ToolName.SCRAPECREATORS,
    ],
    "mechanism_evidence": [
        ToolName.PUBMED,
        ToolName.SERPAPI_SCHOLAR,
        ToolName.TADDY_PODCASTS,
        ToolName.SCRAPLING,
    ],
    "competitor_ads": [
        ToolName.SCRAPECREATORS,
        ToolName.BROWSER_HARNESS,
    ],
    "trending_content": [
        ToolName.GOOGLE_TRENDS,
        ToolName.SCRAPECREATORS,
        ToolName.PRAW_REDDIT,
    ],
    "regulatory": [
        ToolName.FDA_API,
        ToolName.FTC_API,
        ToolName.SCRAPLING,
    ],
    "competitor_pages": [
        ToolName.SCRAPLING,
        ToolName.BROWSER_HARNESS,
    ],
    "cultural_pulse": [
        ToolName.GOOGLE_NEWS_RSS,
        ToolName.PRAW_REDDIT,
        ToolName.GOOGLE_TRENDS,
        ToolName.SCRAPECREATORS,
    ],
    "expert_commentary": [
        ToolName.TADDY_PODCASTS,
        ToolName.YOUTUBE_DATA_API,
        ToolName.SCRAPLING,
    ],
}


def get_tools_for_question(question_type: str) -> list[ToolSpec]:
    """Return tool specs in priority order for a question type."""
    tool_names = TOOL_PRIORITY.get(question_type, [])
    return [TOOL_CATALOG[t] for t in tool_names if t in TOOL_CATALOG]

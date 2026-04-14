"""Platform adapter — transforms ScrapCreators responses into extractor input formats.

Each existing extractor expects a specific JSON shape (e.g., meta_ads expects
``{"ads": [...], "comments": [...]}``). ScrapCreators returns its own format.
This adapter bridges the gap so extractors work unchanged.

Usage:
    from app.services.acquisition.connectors.scrapecreators import scrapecreators_client
    from app.services.acquisition.connectors.platform_adapter import adapt

    raw = await scrapecreators_client.meta.search_ad_library("sleep supplement")
    extractor_input = adapt.meta_ads(raw)  # → {"ads": [...], "comments": [...]}
    result = await MetaAdsExtractor().extract(extractor_input, account_id=...)
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.acquisition.connectors.scrapecreators import PaginatedResponse

logger = logging.getLogger(__name__)


def _safe_int(val: Any, default: int = 0) -> int:
    """Coerce a value to int, handling None/str gracefully."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Meta Ads ───────────────────────────────────────────────────────────


def meta_ads_from_search(ad_search: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Meta ad search → MetaAdsExtractor input.

    MetaAdsExtractor expects: {"ads": [...], "comments": [...]}
    Each ad needs: body.text, ad_creative_link_title, ad_creative_link_description,
                   id, ad_snapshot_url, impressions.lower_bound, spend.lower_bound,
                   page_name, ad_delivery_start_time, publisher_platforms, etc.
    """
    ads = []
    for item in ad_search.data:
        ads.append({
            "id": item.get("id") or item.get("ad_id", ""),
            "body": {"text": item.get("body") or item.get("ad_text") or item.get("message", "")},
            "ad_creative_body": item.get("body") or item.get("ad_text", ""),
            "ad_creative_link_title": item.get("title") or item.get("link_title", ""),
            "ad_creative_link_description": item.get("description") or item.get("link_description", ""),
            "ad_snapshot_url": item.get("snapshot_url") or item.get("ad_url", ""),
            "page_name": item.get("page_name") or item.get("advertiser_name", ""),
            "ad_delivery_start_time": item.get("start_date") or item.get("delivery_start", ""),
            "ad_delivery_stop_time": item.get("end_date") or item.get("delivery_stop"),
            "publisher_platforms": item.get("platforms", []),
            "demographic_distribution": item.get("demographics"),
            "impressions": {
                "lower_bound": _safe_int(item.get("impressions_lower") or item.get("impressions", {}).get("lower_bound")),
            },
            "spend": {
                "lower_bound": _safe_int(item.get("spend_lower") or item.get("spend", {}).get("lower_bound")),
            },
        })

    return {"ads": ads, "comments": []}


def meta_comments(comment_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Meta comments → MetaAdsExtractor input (comments only)."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "id": item.get("id") or item.get("comment_id", ""),
            "message": item.get("text") or item.get("message") or item.get("body", ""),
            "from": {"name": item.get("author") or item.get("from", {}).get("name", "")},
            "created_time": item.get("created_time") or item.get("timestamp", ""),
            "like_count": _safe_int(item.get("likes") or item.get("like_count")),
            "comment_count": _safe_int(item.get("replies") or item.get("reply_count")),
        })

    return {"ads": [], "comments": comments}


# ── TikTok ─────────────────────────────────────────────────────────────


def tiktok_from_videos(video_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators TikTok videos → TikTokExtractor input.

    TikTokExtractor expects: {"videos": [...], "comments": [...], "ads": [...]}
    Each video needs: id, desc/description, share_url, author.uniqueId,
                      stats.playCount/diggCount/commentCount/shareCount/collectCount,
                      challenges, music, video.duration
    """
    videos = []
    for item in video_response.data:
        stats = item.get("stats") or item.get("statistics") or {}
        author = item.get("author") or {}
        if isinstance(author, str):
            author = {"uniqueId": author}

        videos.append({
            "id": item.get("id") or item.get("video_id", ""),
            "desc": item.get("desc") or item.get("description") or item.get("text", ""),
            "description": item.get("desc") or item.get("description", ""),
            "share_url": item.get("share_url") or item.get("url", ""),
            "createTime": item.get("createTime") or item.get("created_at", ""),
            "author": {
                "uniqueId": author.get("uniqueId") or author.get("username") or author.get("unique_id", ""),
            },
            "stats": {
                "playCount": _safe_int(stats.get("playCount") or stats.get("views") or item.get("views")),
                "diggCount": _safe_int(stats.get("diggCount") or stats.get("likes") or item.get("likes")),
                "commentCount": _safe_int(stats.get("commentCount") or stats.get("comments") or item.get("comment_count")),
                "shareCount": _safe_int(stats.get("shareCount") or stats.get("shares") or item.get("shares")),
                "collectCount": _safe_int(stats.get("collectCount") or stats.get("saves") or item.get("saves")),
            },
            "challenges": [
                {"name": h} for h in (item.get("hashtags") or item.get("challenges") or [])
            ],
            "music": {"title": item.get("music") or item.get("sound", "")},
            "video": {"duration": _safe_int(item.get("duration") or item.get("video_duration"))},
            "isAd": item.get("is_ad", False),
        })

    return {"videos": videos, "comments": [], "ads": []}


def tiktok_from_ads(ad_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators TikTok ad search → TikTokExtractor input (ads key)."""
    ads = []
    for item in ad_response.data:
        ads.append({
            "id": item.get("id") or item.get("ad_id", ""),
            "headline": item.get("headline") or item.get("title", ""),
            "description": item.get("description") or item.get("text", ""),
            "landing_page_url": item.get("landing_page") or item.get("url", ""),
            "creative_url": item.get("creative_url") or item.get("video_url", ""),
            "cta": item.get("cta") or item.get("call_to_action", ""),
            "brand_name": item.get("brand") or item.get("advertiser_name", ""),
            "reach": _safe_int(item.get("reach") or item.get("impressions")),
            "like_count": _safe_int(item.get("likes")),
            "start_date": item.get("start_date") or item.get("first_shown", ""),
            "duration_days": _safe_int(item.get("duration") or item.get("days_running")),
        })

    return {"videos": [], "comments": [], "ads": ads}


def tiktok_comments(comment_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators TikTok comments → TikTokExtractor input."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "cid": item.get("id") or item.get("comment_id", ""),
            "text": item.get("text") or item.get("body") or item.get("comment", ""),
            "user": {"uniqueId": item.get("author") or item.get("username", "")},
            "digg_count": _safe_int(item.get("likes") or item.get("digg_count")),
            "reply_count": _safe_int(item.get("replies") or item.get("reply_count")),
            "create_time": item.get("created_at") or item.get("timestamp", ""),
        })

    return {"videos": [], "comments": comments, "ads": []}


# ── YouTube ────────────────────────────────────────────────────────────


def youtube_from_videos(video_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators YouTube videos → YouTubeExtractor input.

    YouTubeExtractor expects: {"videos": [...], "comments": [...]}
    Each video needs: snippet.title, snippet.description, statistics, id
    """
    videos = []
    for item in video_response.data:
        stats = item.get("statistics") or item.get("stats") or {}
        videos.append({
            "id": item.get("id") or item.get("video_id", ""),
            "snippet": {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "channelTitle": item.get("channel") or item.get("channel_title", ""),
                "publishedAt": item.get("published_at") or item.get("upload_date", ""),
                "channelId": item.get("channel_id", ""),
            },
            "statistics": {
                "viewCount": str(_safe_int(stats.get("viewCount") or stats.get("views") or item.get("views"))),
                "likeCount": str(_safe_int(stats.get("likeCount") or stats.get("likes") or item.get("likes"))),
                "commentCount": str(_safe_int(stats.get("commentCount") or stats.get("comments") or item.get("comment_count"))),
            },
        })

    return {"videos": videos, "comments": []}


def youtube_comments(comment_response: PaginatedResponse, channel_id: str = "") -> dict[str, Any]:
    """Transform ScrapCreators YouTube comments → YouTubeExtractor input."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "id": item.get("id") or item.get("comment_id", ""),
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "textDisplay": item.get("text") or item.get("body") or item.get("comment", ""),
                        "textOriginal": item.get("text") or item.get("body", ""),
                        "authorDisplayName": item.get("author") or item.get("username", ""),
                        "likeCount": _safe_int(item.get("likes") or item.get("like_count")),
                        "publishedAt": item.get("published_at") or item.get("timestamp", ""),
                        "videoId": item.get("video_id", ""),
                    },
                },
                "totalReplyCount": _safe_int(item.get("replies") or item.get("reply_count")),
            },
            "replies": {"comments": []},
        })

    return {"videos": [], "comments": comments, "channel_id": channel_id}


# ── Reddit ─────────────────────────────────────────────────────────────


def reddit_from_posts(post_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Reddit posts → RedditExtractor input.

    RedditExtractor expects: {"posts": [...], "comments": [...]}
    Each post needs: data.title, data.selftext, data.subreddit, data.permalink,
                     data.id, data.author, data.score, data.upvote_ratio, etc.
    """
    posts = []
    for item in post_response.data:
        posts.append({
            "data": {
                "id": item.get("id") or item.get("post_id", ""),
                "title": item.get("title", ""),
                "selftext": item.get("selftext") or item.get("body") or item.get("text", ""),
                "subreddit": item.get("subreddit") or item.get("community", ""),
                "permalink": item.get("permalink") or item.get("url", ""),
                "author": item.get("author") or item.get("username", ""),
                "created_utc": item.get("created_utc") or item.get("timestamp", ""),
                "score": _safe_int(item.get("score") or item.get("upvotes")),
                "upvote_ratio": _safe_float(item.get("upvote_ratio"), 0.5),
                "num_comments": _safe_int(item.get("num_comments") or item.get("comment_count")),
                "total_awards_received": _safe_int(item.get("awards")),
                "link_flair_text": item.get("flair") or item.get("link_flair_text"),
                "is_self": item.get("is_self", True),
            },
        })

    return {"posts": posts, "comments": []}


def reddit_comments(comment_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Reddit comments → RedditExtractor input."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "data": {
                "id": item.get("id") or item.get("comment_id", ""),
                "body": item.get("body") or item.get("text") or item.get("comment", ""),
                "author": item.get("author") or item.get("username", ""),
                "score": _safe_int(item.get("score") or item.get("upvotes")),
                "created_utc": item.get("created_utc") or item.get("timestamp", ""),
                "permalink": item.get("permalink", ""),
                "parent_id": item.get("parent_id", ""),
                "subreddit": item.get("subreddit", ""),
                "is_submitter": item.get("is_submitter", False),
            },
        })

    return {"posts": [], "comments": comments}


# ── Amazon ─────────────────────────────────────────────────────────────


def amazon_reviews(review_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Amazon reviews → AmazonReviewExtractor input.

    AmazonReviewExtractor expects: {"reviews": [...]}
    Each review needs: title, body/text, rating/stars, helpful_votes,
                       verified_purchase, id, author_name, date, url, asin
    """
    reviews = []
    for item in review_response.data:
        reviews.append({
            "id": item.get("id") or item.get("review_id", ""),
            "title": item.get("title", ""),
            "body": item.get("body") or item.get("text") or item.get("review_text", ""),
            "text": item.get("body") or item.get("text", ""),
            "rating": _safe_int(item.get("rating") or item.get("stars")),
            "stars": _safe_int(item.get("rating") or item.get("stars")),
            "helpful_votes": _safe_int(item.get("helpful_votes") or item.get("helpful_count")),
            "verified_purchase": item.get("verified_purchase") or item.get("verified", False),
            "vine_review": item.get("vine", False),
            "author_name": item.get("author") or item.get("reviewer_name", ""),
            "date": item.get("date") or item.get("review_date", ""),
            "url": item.get("url") or item.get("review_url", ""),
            "asin": item.get("asin") or item.get("product_id", ""),
        })

    return {"reviews": reviews}


# ── Instagram ──────────────────────────────────────────────────────────


def instagram_from_posts(post_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Instagram posts → generic extraction input."""
    posts = []
    for item in post_response.data:
        posts.append({
            "id": item.get("id") or item.get("post_id", ""),
            "caption": item.get("caption") or item.get("text", ""),
            "author": item.get("author") or item.get("username", ""),
            "timestamp": item.get("timestamp") or item.get("taken_at", ""),
            "likes": _safe_int(item.get("likes") or item.get("like_count")),
            "comments_count": _safe_int(item.get("comments") or item.get("comment_count")),
            "media_type": item.get("media_type", "image"),
            "url": item.get("url") or item.get("permalink", ""),
            "hashtags": item.get("hashtags", []),
        })

    return {"posts": posts, "comments": []}


def instagram_comments(comment_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Instagram comments → generic extraction input."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "id": item.get("id") or item.get("comment_id", ""),
            "text": item.get("text") or item.get("body") or item.get("comment", ""),
            "author": item.get("author") or item.get("username", ""),
            "timestamp": item.get("timestamp") or item.get("created_at", ""),
            "likes": _safe_int(item.get("likes") or item.get("like_count")),
        })

    return {"posts": [], "comments": comments}


# ── Twitter/X ──────────────────────────────────────────────────────────


def twitter_from_tweets(tweet_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators tweets → generic extraction input."""
    tweets = []
    for item in tweet_response.data:
        tweets.append({
            "id": item.get("id") or item.get("tweet_id", ""),
            "text": item.get("text") or item.get("full_text") or item.get("body", ""),
            "author": item.get("author") or item.get("username") or item.get("screen_name", ""),
            "timestamp": item.get("created_at") or item.get("timestamp", ""),
            "likes": _safe_int(item.get("likes") or item.get("favorite_count")),
            "retweets": _safe_int(item.get("retweets") or item.get("retweet_count")),
            "replies": _safe_int(item.get("replies") or item.get("reply_count")),
            "quotes": _safe_int(item.get("quotes") or item.get("quote_count")),
            "views": _safe_int(item.get("views") or item.get("impression_count")),
            "url": item.get("url") or item.get("tweet_url", ""),
            "is_reply": item.get("is_reply", False),
            "is_quote": item.get("is_quote", False),
        })

    return {"tweets": tweets, "comments": []}


# ── LinkedIn ───────────────────────────────────────────────────────────


def linkedin_from_posts(post_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators LinkedIn posts → generic extraction input."""
    posts = []
    for item in post_response.data:
        posts.append({
            "id": item.get("id") or item.get("post_id", ""),
            "text": item.get("text") or item.get("body") or item.get("commentary", ""),
            "author": item.get("author") or item.get("author_name", ""),
            "author_headline": item.get("author_headline", ""),
            "timestamp": item.get("timestamp") or item.get("published_at", ""),
            "likes": _safe_int(item.get("likes") or item.get("reaction_count")),
            "comments_count": _safe_int(item.get("comments") or item.get("comment_count")),
            "shares": _safe_int(item.get("shares") or item.get("repost_count")),
            "url": item.get("url") or item.get("post_url", ""),
        })

    return {"posts": posts, "comments": []}


def linkedin_comments(comment_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators LinkedIn comments → generic extraction input."""
    comments = []
    for item in comment_response.data:
        comments.append({
            "id": item.get("id") or item.get("comment_id", ""),
            "text": item.get("text") or item.get("body") or item.get("comment", ""),
            "author": item.get("author") or item.get("author_name", ""),
            "timestamp": item.get("timestamp") or item.get("created_at", ""),
            "likes": _safe_int(item.get("likes") or item.get("reaction_count")),
        })

    return {"posts": [], "comments": comments}


# ── Trustpilot ─────────────────────────────────────────────────────────


def trustpilot_reviews(review_response: PaginatedResponse) -> dict[str, Any]:
    """Transform ScrapCreators Trustpilot reviews → extraction input."""
    reviews = []
    for item in review_response.data:
        reviews.append({
            "id": item.get("id") or item.get("review_id", ""),
            "title": item.get("title", ""),
            "body": item.get("body") or item.get("text") or item.get("review_text", ""),
            "rating": _safe_int(item.get("rating") or item.get("stars")),
            "author": item.get("author") or item.get("reviewer_name", ""),
            "date": item.get("date") or item.get("created_at", ""),
            "verified": item.get("verified", False),
            "company_response": item.get("company_response") or item.get("reply"),
            "url": item.get("url", ""),
        })

    return {"reviews": reviews}


# ── Convenience namespace ──────────────────────────────────────────────


class PlatformAdapter:
    """Namespace for all adapter functions.

    Usage:
        adapt = PlatformAdapter()
        extractor_input = adapt.meta_ads(raw_response)
    """

    meta_ads = staticmethod(meta_ads_from_search)
    meta_comments = staticmethod(meta_comments)
    tiktok_videos = staticmethod(tiktok_from_videos)
    tiktok_ads = staticmethod(tiktok_from_ads)
    tiktok_comments = staticmethod(tiktok_comments)
    youtube_videos = staticmethod(youtube_from_videos)
    youtube_comments = staticmethod(youtube_comments)
    reddit_posts = staticmethod(reddit_from_posts)
    reddit_comments = staticmethod(reddit_comments)
    amazon_reviews = staticmethod(amazon_reviews)
    instagram_posts = staticmethod(instagram_from_posts)
    instagram_comments = staticmethod(instagram_comments)
    twitter_tweets = staticmethod(twitter_from_tweets)
    linkedin_posts = staticmethod(linkedin_from_posts)
    linkedin_comments = staticmethod(linkedin_comments)
    trustpilot_reviews = staticmethod(trustpilot_reviews)


adapt = PlatformAdapter()

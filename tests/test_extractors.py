"""Tests for all platform extractors."""

import pytest

from app.workers.extractors.base import BaseExtractor, ExtractionResult, SourcePlatform


# ── YouTube ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_youtube_comments():
    from app.workers.extractors.youtube import YouTubeExtractor

    extractor = YouTubeExtractor()
    assert extractor.platform == SourcePlatform.YOUTUBE

    result = await extractor.extract(
        {"comments": [
            {"snippet": {"topLevelComment": {"snippet": {
                "textDisplay": "This supplement actually helped my sleep issues",
                "authorDisplayName": "TestUser",
                "likeCount": 5,
                "videoId": "abc123",
            }}, "totalReplyCount": 2}},
            {"snippet": {"topLevelComment": {"snippet": {
                "textDisplay": "ok",  # too short
            }}}},
        ]},
        account_id="acct_test",
    )

    assert isinstance(result, ExtractionResult)
    assert result.extracted_count == 1
    assert result.skipped_count == 1
    assert result.payloads[0].exact_quote is True
    assert "sleep" in result.payloads[0].content


# ── Reddit ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reddit_posts():
    from app.workers.extractors.reddit import RedditExtractor

    extractor = RedditExtractor()
    result = await extractor.extract(
        {"posts": [
            {
                "title": "Anyone tried adaptogens for cortisol?",
                "selftext": "I've been dealing with 3am wakeups for months now",
                "score": 42,
                "subreddit": "Supplements",
                "author": "user123",
                "num_comments": 15,
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count >= 1
    assert any("cortisol" in p.content for p in result.payloads)


# ── Twitter/X ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_twitter_tweets():
    from app.workers.extractors.twitter_x import TwitterXExtractor

    extractor = TwitterXExtractor()
    assert extractor.platform == SourcePlatform.TWITTER_X

    result = await extractor.extract(
        {"tweets": [
            {
                "text": "Just discovered this supplement and my sleep has completely changed",
                "id": "123456",
                "public_metrics": {"like_count": 100, "retweet_count": 20, "reply_count": 5, "quote_count": 3, "bookmark_count": 15},
                "author": {"username": "healthguru"},
                "created_at": "2026-04-01T12:00:00Z",
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count == 1
    assert result.payloads[0].engagement["bookmarks"] == 15


# ── Instagram ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_instagram_posts():
    from app.workers.extractors.instagram import InstagramExtractor

    extractor = InstagramExtractor()
    result = await extractor.extract(
        {"posts": [
            {
                "caption": "Finally sleeping through the night #supplements #health #cortisol",
                "likes": 500,
                "comments": 30,
                "saves": 45,
                "type": "image",
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count == 1
    assert "cortisol" in result.payloads[0].platform_metadata.get("hashtags", [])


# ── Facebook ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_facebook_ads():
    from app.workers.extractors.facebook import FacebookExtractor

    extractor = FacebookExtractor()
    result = await extractor.extract(
        {"ads": [
            {
                "ad_creative_bodies": ["Tired of waking up at 3am? Your cortisol might be the problem."],
                "page_name": "SupplementBrand",
                "ad_delivery_start_time": "2026-03-01",
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count == 1
    assert result.payloads[0].suggested_category == "hook"


# ── Trustpilot ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trustpilot_reviews():
    from app.workers.extractors.trustpilot import TrustpilotExtractor

    extractor = TrustpilotExtractor()
    result = await extractor.extract(
        {"reviews": [
            {
                "title": "Life changing product",
                "text": "After 3 weeks I noticed a huge difference in my sleep quality and energy levels.",
                "rating": 5,
                "isVerified": True,
                "consumer": {"displayName": "Jane D."},
            },
            {
                "title": "Didn't work for me",
                "text": "Tried it for a month, no difference at all. Waste of money.",
                "rating": 1,
                "isVerified": True,
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count == 2
    assert result.payloads[0].confidence == 0.9  # verified
    assert result.payloads[1].suggested_category == "objection"  # low rating


# ── App Store ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_store_reviews():
    from app.workers.extractors.app_store import AppStoreExtractor

    extractor = AppStoreExtractor()
    result = await extractor.extract(
        {"reviews": [
            {
                "title": "Best sleep tracking app",
                "body": "This app helped me understand my sleep patterns and improve my routine.",
                "rating": 5,
                "version": "3.2.1",
                "userName": "SleepyUser",
            },
        ]},
        account_id="acct_test",
    )

    assert result.extracted_count == 1
    assert result.payloads[0].platform_metadata["version"] == "3.2.1"


# ── All Extractors Have Platform ────────────────────────────────────

def test_all_extractors_have_platform():
    """Every extractor must define a SourcePlatform."""
    import importlib
    import pkgutil
    import app.workers.extractors as pkg

    for _, name, _ in pkgutil.iter_modules(pkg.__path__):
        if name == "base":
            continue
        mod = importlib.import_module(f"app.workers.extractors.{name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseExtractor) and attr is not BaseExtractor:
                assert hasattr(attr, "platform"), f"{attr.__name__} missing platform"
                assert isinstance(attr.platform, SourcePlatform), f"{attr.__name__}.platform not SourcePlatform"

"""Twitter/X extractor — tweets, quote tweets, reply chains, engagement.

Extracts from tweet data with X-specific engagement patterns:
high bookmark rate = save-worthy content, high quote-tweet rate =
strong opinion/contrarian content, reply chains reveal objections.
"""

from __future__ import annotations

from typing import Any

from app.workers.extractors.base import (
    BaseExtractor,
    ExtractionPayload,
    ExtractionResult,
    SourcePlatform,
)


class TwitterXExtractor(BaseExtractor):
    platform = SourcePlatform.TWITTER_X

    async def extract(
        self,
        raw_data: Any,
        *,
        account_id: str,
        offer_id: str | None = None,
    ) -> ExtractionResult:
        payloads: list[ExtractionPayload] = []
        skipped = 0

        tweets = raw_data.get("tweets", [])
        if isinstance(raw_data, list):
            tweets = raw_data

        for tweet in tweets:
            text = tweet.get("text", "") or tweet.get("full_text", "")
            if not text or len(text.split()) < 3:
                skipped += 1
                continue

            metrics = tweet.get("public_metrics", {}) or tweet.get("metrics", {})
            likes = metrics.get("like_count", 0) or metrics.get("likes", 0)
            retweets = metrics.get("retweet_count", 0) or metrics.get("retweets", 0)
            replies = metrics.get("reply_count", 0) or metrics.get("replies", 0)
            quotes = metrics.get("quote_count", 0) or metrics.get("quotes", 0)
            bookmarks = metrics.get("bookmark_count", 0) or metrics.get("bookmarks", 0)

            tweet_id = tweet.get("id", "") or tweet.get("tweet_id", "")
            author = tweet.get("author", {})
            author_name = (
                author.get("username", "")
                or author.get("screen_name", "")
                or tweet.get("username", "")
            )

            # Determine extraction type
            is_reply = bool(tweet.get("in_reply_to_user_id") or tweet.get("is_reply"))
            is_quote = bool(tweet.get("quoted_tweet") or tweet.get("is_quote_tweet"))
            extraction_type = "reply" if is_reply else ("quote_tweet" if is_quote else "tweet")

            # Category hints based on engagement patterns
            suggested = None
            if bookmarks > likes * 0.1:
                suggested = "proof"  # High bookmark rate = reference-worthy
            elif quotes > retweets * 0.5:
                suggested = "hook"  # High quote rate = strong opinion trigger

            payloads.append(ExtractionPayload(
                content=text,
                source_platform=self.platform,
                extraction_type=extraction_type,
                exact_quote=True,
                source_url=f"https://x.com/{author_name}/status/{tweet_id}" if author_name else None,
                source_id=str(tweet_id),
                author=author_name,
                timestamp=tweet.get("created_at"),
                engagement={
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                    "quotes": quotes,
                    "bookmarks": bookmarks,
                },
                platform_metadata={
                    "is_reply": is_reply,
                    "is_quote_tweet": is_quote,
                    "is_thread": bool(tweet.get("conversation_id")),
                    "has_media": bool(tweet.get("attachments") or tweet.get("media")),
                    "language": tweet.get("lang"),
                },
                suggested_category=suggested,
            ))

        return ExtractionResult(
            platform=self.platform,
            payloads=payloads,
            raw_count=len(tweets),
            extracted_count=len(payloads),
            skipped_count=skipped,
        )

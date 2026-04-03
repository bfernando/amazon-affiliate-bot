#!/usr/bin/env python3
"""
Twitter Analytics Tracker
Fetches metrics for the last 20 tweets and calculates engagement scores.
Saves results to analytics.csv and prints a top-5 summary table.
"""
import csv
import os
from pathlib import Path

import tweepy
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

ANALYTICS_CSV = BASE_DIR / "analytics.csv"


def get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
        bearer_token=os.environ["TWITTER_BEARER_TOKEN"],
    )


def fetch_tweet_metrics(client: tweepy.Client, count: int = 20) -> list:
    me = client.get_me()
    user_id = me.data.id

    response = client.get_users_tweets(
        user_id,
        max_results=max(count, 5),
        tweet_fields=["public_metrics", "non_public_metrics", "created_at", "text"],
    )

    if not response.data:
        return []

    tweets = []
    for tweet in response.data[:count]:
        pm = tweet.public_metrics or {}
        npm = tweet.non_public_metrics or {}

        likes = pm.get("like_count", 0)
        retweets = pm.get("retweet_count", 0)
        replies = pm.get("reply_count", 0)
        bookmarks = pm.get("bookmark_count", 0)
        impressions = npm.get("impression_count", pm.get("impression_count", 0))

        engagement_score = round(
            likes * 1 + retweets * 20 + replies * 13.5 + bookmarks * 10, 1
        )

        tweets.append({
            "tweet_id": str(tweet.id),
            "created_at": str(tweet.created_at),
            "text": tweet.text,
            "impressions": impressions,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
            "bookmarks": bookmarks,
            "engagement_score": engagement_score,
        })

    return tweets


def save_to_csv(tweets: list):
    fields = [
        "tweet_id", "created_at", "text", "impressions",
        "likes", "retweets", "replies", "bookmarks", "engagement_score",
    ]
    with open(ANALYTICS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(tweets)
    print(f"Saved {len(tweets)} tweets to {ANALYTICS_CSV}")


def print_summary(tweets: list):
    if not tweets:
        print("No tweets to display.")
        return

    sorted_tweets = sorted(tweets, key=lambda x: x["engagement_score"], reverse=True)

    print("\n" + "=" * 80)
    print("TOP 5 TWEETS BY ENGAGEMENT SCORE")
    print("=" * 80)
    for i, t in enumerate(sorted_tweets[:5], 1):
        preview = t["text"][:65].replace("\n", " ")
        if len(t["text"]) > 65:
            preview += "..."
        print(f"\n#{i}  Score: {t['engagement_score']}")
        print(f"    {preview}")
        print(
            f"    ❤️  {t['likes']}  🔁 {t['retweets']}  "
            f"💬 {t['replies']}  🔖 {t['bookmarks']}"
            + (f"  👁️  {t['impressions']}" if t["impressions"] else "")
        )
        print(f"    {t['created_at']}")

    print("\n" + "=" * 80)
    total = len(tweets)
    avg = sum(t["engagement_score"] for t in tweets) / total
    print(f"Tweets analyzed: {total}  |  Avg engagement score: {avg:.1f}")
    print("=" * 80 + "\n")


def main():
    print("Fetching Twitter analytics...")
    client = get_client()
    tweets = fetch_tweet_metrics(client, count=20)

    if not tweets:
        print("No tweets found.")
        return

    save_to_csv(tweets)
    print_summary(tweets)


if __name__ == "__main__":
    main()

"""
Twitter/X Deal Account Monitor
Pulls recent tweets from Amazon deal-focused accounts and extracts affiliate deals.
"""
import re
import os
import logging
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv
from src.config import config

log = logging.getLogger(__name__)

# Accounts that regularly post Amazon tech deals
DEAL_ACCOUNTS = [
    "amazondeals",
    "9to5toys",
    "SlickDeals",
    "DealNewsDeals",
    "TechDealsTweet",
    "Woot",
    "BestBuy",
    "dealspotr",
]

# ASIN extraction patterns
ASIN_PATTERNS = [
    r'/dp/([A-Z0-9]{10})',
    r'/gp/product/([A-Z0-9]{10})',
    r'asin=([A-Z0-9]{10})',
    r'/([A-Z0-9]{10})(?:/|\?|$)',
]

# Amazon URL patterns (including short links)
AMAZON_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:amazon\.com|amzn\.to|amzn\.com)[^\s"\'<>)\]]*'
)

PRICE_PATTERN = re.compile(r'\$\s*([\d,]+\.?\d*)')
DISCOUNT_PATTERN = re.compile(r'(\d+)\s*%\s*off', re.IGNORECASE)
WAS_PRICE_PATTERN = re.compile(
    r'(?:was|reg|regular|orig(?:inal)?|retail|list)[:\s]+\$\s*([\d,]+\.?\d*)',
    re.IGNORECASE
)


def extract_asin(url: str) -> Optional[str]:
    for pattern in ASIN_PATTERNS:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            asin = match.group(1).upper()
            if re.match(r'^[A-Z0-9]{10}$', asin):
                return asin
    return None


def parse_prices(text: str):
    """Return (current_price, original_price, discount_pct) from tweet text."""
    prices = []
    for m in PRICE_PATTERN.finditer(text):
        try:
            prices.append(float(m.group(1).replace(',', '')))
        except ValueError:
            pass

    discount_match = DISCOUNT_PATTERN.search(text)
    discount_pct = int(discount_match.group(1)) if discount_match else 0

    was_match = WAS_PRICE_PATTERN.search(text)
    original_price = float(was_match.group(1).replace(',', '')) if was_match else 0.0

    current_price = min(prices) if prices else 0.0

    # If we have current price + discount but no was price, calculate it
    if current_price > 0 and discount_pct > 0 and original_price == 0:
        original_price = round(current_price / (1 - discount_pct / 100), 2)

    # If we have two prices and no explicit discount, calculate it
    if len(prices) >= 2 and discount_pct == 0:
        current_price = min(prices)
        original_price = max(prices)
        if original_price > 0:
            discount_pct = int((1 - current_price / original_price) * 100)

    return current_price, original_price, discount_pct


def get_twitter_deals(min_discount: int = 20) -> List:
    """
    Pull recent tweets from deal accounts and extract Amazon affiliate deals.
    Returns a list of Deal-like dicts compatible with the main deal pipeline.
    """
    try:
        import tweepy
    except ImportError:
        log.warning("tweepy not installed — skipping Twitter deals source")
        return []

    # Import Deal here to avoid circular imports
    try:
        from src.scraper.deals import Deal
    except ImportError:
        try:
            from deals import Deal
        except ImportError:
            log.warning("Could not import Deal class — skipping Twitter deals")
            return []

    load_dotenv(Path.home() / "projects" / ".env.shared")
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not bearer_token:
        log.warning("TWITTER_BEARER_TOKEN not set — skipping Twitter deals source")
        return []

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
    deals: List[Deal] = []
    seen_asins: set = set()

    for username in DEAL_ACCOUNTS:
        try:
            # Look up user ID
            user_resp = client.get_user(username=username)
            if not user_resp.data:
                log.debug(f"User not found: {username}")
                continue
            user_id = user_resp.data.id

            # Fetch recent tweets with URLs expanded
            tweets_resp = client.get_users_tweets(
                id=user_id,
                max_results=20,
                tweet_fields=["text", "entities", "created_at"],
                expansions=["attachments.media_keys"],
            )
            if not tweets_resp.data:
                log.debug(f"No tweets for {username}")
                continue

            for tweet in tweets_resp.data:
                text = tweet.text

                # Find Amazon URLs in tweet text
                amazon_urls = AMAZON_URL_PATTERN.findall(text)

                # Also check expanded URLs from entities
                if tweet.entities and "urls" in tweet.entities:
                    for url_obj in tweet.entities["urls"]:
                        expanded = url_obj.get("expanded_url", "")
                        if "amazon.com" in expanded or "amzn.to" in expanded:
                            amazon_urls.append(expanded)

                for url in amazon_urls:
                    asin = extract_asin(url)
                    if not asin or asin in seen_asins:
                        continue

                    current_price, original_price, discount_pct = parse_prices(text)

                    # Skip if discount too low or no price info
                    if discount_pct < min_discount:
                        continue
                    if current_price <= 0:
                        continue

                    seen_asins.add(asin)
                    affiliate_url = config.generate_affiliate_link(asin)

                    # Use tweet text as title (truncated)
                    title = text[:120].split('\n')[0].strip()

                    deal = Deal(
                        title=title,
                        asin=asin,
                        current_price=current_price,
                        original_price=original_price if original_price > 0 else current_price,
                        discount_percent=discount_pct,
                        rating=0.0,
                        review_count=0,
                        image_url="",
                        url=affiliate_url,
                        affiliate_url=affiliate_url,
                        deal_type="twitter_deal",
                        source=f"@{username}",
                    )
                    deals.append(deal)
                    log.info(f"Twitter deal found from @{username}: {asin} — {discount_pct}% off ${current_price}")

        except tweepy.errors.TooManyRequests:
            log.warning(f"Rate limited fetching @{username} — skipping")
            continue
        except tweepy.errors.TweepyException as e:
            log.debug(f"Error fetching @{username}: {e}")
            continue
        except Exception as e:
            log.debug(f"Unexpected error for @{username}: {e}")
            continue

    log.info(f"Twitter deals found: {len(deals)} across {len(DEAL_ACCOUNTS)} accounts")
    return deals

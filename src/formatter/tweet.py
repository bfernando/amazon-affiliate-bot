"""Format deals into concise tweet-ready text for X."""

import re
from typing import List
from urllib.parse import urlparse, urlunparse

from src.config import config
from src.scraper.deals import Deal


DISCLOSURE = "#ad #affiliate"
BASE_HASHTAGS = "#AmazonDeals #TechDeals"
MAX_TWEET_LEN = 280


def _short_title(title: str, max_len: int = 96) -> str:
    title = " ".join(title.split())
    title = re.sub(r"^(?:\d+(?:\.\d+)?%\s*OFF\s*[-:]?\s*)+", "", title, flags=re.IGNORECASE)
    if len(title) <= max_len:
        return title
    return title[: max_len - 3].rstrip() + "..."


def _price_line(deal: Deal) -> str:
    current = f"${deal.current_price:,.2f}"
    if deal.original_price and deal.original_price > deal.current_price:
        original = f"${deal.original_price:,.2f}"
        return f"Now {current} (was {original})"
    return f"Now {current}"


def _truncate(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3].rstrip() + "..."


def _safe_affiliate_url(deal: Deal) -> str:
    raw = (deal.affiliate_url or "").strip()
    parsed = urlparse(raw)
    has_valid_http = parsed.scheme in {"http", "https"} and bool(parsed.netloc) and bool(parsed.path)
    looks_like_amazon = "amazon." in (parsed.netloc or "").lower()

    if has_valid_http and looks_like_amazon:
        # Drop URL fragments for cleaner card/facet parsing on X.
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))

    if deal.asin:
        return config.generate_affiliate_link(deal.asin)

    # Fallback only when ASIN is unavailable.
    return raw


def _fit_headline(headline: str, trailing_lines: List[str]) -> str:
    reserved = sum(len(line) for line in trailing_lines) + len(trailing_lines)  # newline separators
    max_headline = MAX_TWEET_LEN - reserved
    return _truncate(headline, max_headline)


def format_deal_tweet(deal: Deal) -> str:
    """Format a single deal into a concise tweet."""
    title = _short_title(deal.title)
    discount = f"{deal.discount_percent}% OFF - " if deal.discount_percent > 0 else ""
    affiliate_url = _safe_affiliate_url(deal)
    trailing_lines = [
        _price_line(deal),
        DISCLOSURE,
        affiliate_url,
        BASE_HASHTAGS,
    ]
    headline = _fit_headline(f"{discount}{title}", trailing_lines)

    parts = [headline, *trailing_lines]
    return "\n".join(parts)


def format_deal_thread(deals: List[Deal]) -> List[str]:
    """Format multiple deals into a short thread."""
    if not deals:
        return []

    tweets: List[str] = []
    best_discount = max(d.discount_percent for d in deals)
    tweets.append(
        f"Tech Deals Thread\n"
        f"{len(deals)} picks, up to {best_discount}% off.\n"
        f"{DISCLOSURE}"
    )

    for i, deal in enumerate(deals[:10], 1):
        title = _short_title(deal.title, max_len=84)
        line = _price_line(deal)
        affiliate_url = _safe_affiliate_url(deal)
        trailing_lines = [line, DISCLOSURE, affiliate_url]
        headline = _fit_headline(f"{i}/{len(deals)} {title}", trailing_lines)
        tweets.append("\n".join([headline, *trailing_lines]))

    tweets.append(f"Follow for daily deals.\n{DISCLOSURE}\n{BASE_HASHTAGS}")
    return tweets


def format_single_best_deal(deal: Deal) -> str:
    """Format the single best deal as a standalone tweet."""
    return format_deal_tweet(deal)


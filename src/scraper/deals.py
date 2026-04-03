"""RSS-based Amazon deal scraper - pulls tech deals from aggregator sites."""
import re
import feedparser
import httpx
import requests
from typing import List, Optional
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from rich.console import Console
from src.config import config

console = Console()

RSS_FEEDS = [
    # Reddit deal subreddits (50 posts each)
    "https://www.reddit.com/r/buildapcsales/.rss?limit=50",
    "https://www.reddit.com/r/GameDeals/.rss?limit=50",
    "https://www.reddit.com/r/techdeals/.rss?limit=50",
    "https://www.reddit.com/r/deals/.rss?limit=50",
    "https://www.reddit.com/r/hardware/.rss?limit=50",
    "https://www.reddit.com/r/gadgets/.rss?limit=50",
    "https://www.reddit.com/r/headphones/.rss?limit=50",
    "https://www.reddit.com/r/homeautomation/.rss?limit=50",
    "https://www.reddit.com/r/frugal/.rss?limit=50",
    "https://www.reddit.com/r/PCDeals/.rss?limit=50",
    # Slickdeals hottest deals
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    # DealNews Electronics
    "https://www.dealnews.com/c142/Electronics/?rss=1",
]

BESTSELLER_PAGES = [
    ("electronics", "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics"),
    ("computers", "https://www.amazon.com/Best-Sellers-Computers-Accessories/zgbs/pc"),
]

TECH_KEYWORDS = [
    "laptop", "monitor", "keyboard", "mouse", "headphone", "earbuds",
    "bluetooth speaker", "tablet", "ipad", "kindle", "echo dot", "fire tv",
    "fire stick", "webcam", "printer", "router", "wifi", "ssd", "nvme",
    "hard drive", "hdd", "usb hub", "usb-c", "charger", "power bank",
    "microphone", "gpu", "graphics card", "cpu", "processor", "ram", "ddr",
    "gaming", "playstation", "xbox", "nintendo", "switch", "iphone", "samsung galaxy",
    "pixel", "smartwatch", "airpods", "dell", "hp laptop", "lenovo", "thinkpad",
    "asus", "acer", "logitech", "anker", "bose", "sony wh", "sony wf", "lg monitor",
    "computer", "pc build", "macbook", "imac", "mac mini", "smart plug",
    "smart bulb", "ring doorbell", "nest", "alexa", "google home",
    "mechanical keyboard", "gaming mouse", "gaming headset", "cooling pad",
    "docking station", "display", "projector", "dash cam",
]

# Words that indicate NON-tech deals — skip these
EXCLUDE_KEYWORDS = [
    "glass", "food", "kitchen", "cookware", "clothing", "shoes", "shirt",
    "pants", "jacket", "vitamin", "supplement", "mattress", "bedding",
    "furniture", "vacuum", "blender", "coffee maker", "storage container",
    "beauty", "skincare", "makeup", "toy", "books", "paperback", "hardcover",
    "garden", "tools",
]


@dataclass
class Deal:
    title: str
    asin: str
    current_price: float
    original_price: float
    discount_percent: int
    rating: float
    review_count: int
    image_url: str
    url: str
    affiliate_url: str
    is_prime: bool = False
    is_amazon_shipped: bool = True
    category: str = "tech"
    deal_type: str = "rss_deal"
    source: str = ""
    description: str = ""


def extract_asin(url: str) -> Optional[str]:
    """Extract ASIN from an Amazon URL."""
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/exec/obidos/ASIN/([A-Z0-9]{10})',
        r'asin=([A-Z0-9]{10})',
        r'/([A-Z0-9]{10})(?:/|\?|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            asin = match.group(1).upper()
            if re.match(r'^[A-Z0-9]{10}$', asin):
                return asin
    return None


def build_affiliate_url(asin: str) -> str:
    """Build Amazon affiliate URL from ASIN."""
    return config.generate_affiliate_link(asin)


def extract_amazon_urls(text: str) -> List[str]:
    """Find all Amazon URLs in text."""
    pattern = r'https?://(?:www\.)?amazon\.com[^\s"\'<>)]*'
    return re.findall(pattern, text)


def parse_price(text: str) -> float:
    """Extract first price found in text."""
    match = re.search(r'\$\s*([\d,]+\.?\d*)', text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 0.0


def parse_discount(text: str) -> float:
    """Extract discount percentage from deal text using multiple strategies."""
    t = text.lower()

    # Strategy 1: explicit percent string
    m = re.search(r'(\d+)\s*%\s*off', t)
    if m:
        return float(m.group(1))
    m = re.search(r'save\s+(\d+)\s*%', t)
    if m:
        return float(m.group(1))
    m = re.search(r'-\s*(\d+)\s*%', t)
    if m:
        return float(m.group(1))

    # Strategy 2: "was $X now $Y" / "reg $X sale $Y" / "from $X to $Y"
    was_now = re.search(
        r'(?:was|reg(?:ular)?|orig(?:inal)?|from|retail|msrp|list)\s*:?\s*\$?([\d,]+(?:\.\d+)?)'
        r'.*?(?:now|sale|down to|for|only|just)\s*:?\s*\$?([\d,]+(?:\.\d+)?)',
        t
    )
    if was_now:
        try:
            orig = float(was_now.group(1).replace(',', ''))
            sale = float(was_now.group(2).replace(',', ''))
            if orig > 0 and 0 < sale < orig:
                return round((orig - sale) / orig * 100, 1)
        except ValueError:
            pass

    # Strategy 3: two dollar amounts in sequence — "$999 $649"
    prices = re.findall(r'\$\s*([\d,]+(?:\.\d+)?)', t)
    if len(prices) >= 2:
        try:
            orig = float(prices[0].replace(',', ''))
            sale = float(prices[1].replace(',', ''))
            if orig > sale > 0 and orig < 10000:
                return round((orig - sale) / orig * 100, 1)
        except ValueError:
            pass

    return 0.0


MIN_DISCOUNT = 20  # Only post deals with 20%+ off


def is_tech_deal(title: str, description: str = "") -> bool:
    """Check if this is a tech-related deal and not a non-tech item."""
    combined = (title + " " + description).lower()
    # Reject if it contains non-tech keywords
    if any(kw in combined for kw in EXCLUDE_KEYWORDS):
        return False
    return any(kw in combined for kw in TECH_KEYWORDS)


class AmazonDealScraper:
    """Scrape Amazon tech deals from RSS feed aggregators."""

    def __init__(self):
        self.seen_asins = set()

    async def get_tech_deals(self, limit_per_category: int = 10) -> List[Deal]:
        """Fetch deals from all RSS feeds and Twitter/X deal accounts."""
        all_deals = []

        for feed_url in RSS_FEEDS:
            source = feed_url.split('/')[2].replace('www.', '')
            console.print(f"[cyan]Fetching deals from {source}...[/cyan]")
            try:
                deals = await self._fetch_feed(feed_url, source, limit=limit_per_category)
                all_deals.extend(deals)
                console.print(f"  Found {len(deals)} deals from {source}")
            except Exception as e:
                console.print(f"  [red]Error fetching {source}: {e}[/red]")

        # Pull additional deals from Twitter/X deal accounts
        try:
            from src.scraper.twitter_deals import get_twitter_deals
            console.print("[cyan]Fetching deals from Twitter/X deal accounts...[/cyan]")
            twitter_deals = get_twitter_deals(min_discount=20)
            all_deals.extend(twitter_deals)
            console.print(f"  Found {len(twitter_deals)} Twitter deals")
        except Exception as e:
            console.print(f"  [yellow]Twitter deals skipped: {e}[/yellow]")

        # Filter to 20%+ off only and must have a real price
        all_deals = [d for d in all_deals if d.discount_percent >= MIN_DISCOUNT and d.current_price > 0]

        # Deduplicate by ASIN
        seen = set()
        unique = []
        for deal in all_deals:
            if deal.asin not in seen:
                seen.add(deal.asin)
                unique.append(deal)

        # Sort by discount
        unique.sort(key=lambda d: d.discount_percent, reverse=True)
        console.print(f"[green]Total unique deals: {len(unique)}[/green]")
        return unique

    async def get_bestseller_deals(self, limit_per_category: int = 5) -> List[Deal]:
        """Fetch Amazon tech best sellers as a fallback source when deals are dry."""
        all_deals = []
        seen = set()

        for category, page_url in BESTSELLER_PAGES:
            console.print(f"[cyan]Fetching Amazon best sellers from {category}...[/cyan]")
            try:
                deals = await self._fetch_bestseller_page(page_url, category, limit=limit_per_category)
                for deal in deals:
                    if deal.asin not in seen:
                        all_deals.append(deal)
                        seen.add(deal.asin)
                console.print(f"  Found {len(deals)} bestseller items from {category}")
            except Exception as e:
                console.print(f"  [red]Error fetching Amazon best sellers for {category}: {e}[/red]")

        all_deals.sort(key=lambda d: (d.review_count, d.rating), reverse=True)
        console.print(f"[green]Total unique bestseller items: {len(all_deals)}[/green]")
        return all_deals

    async def search_deals(self, query: str, limit: int = 15) -> List[Deal]:
        """Search deals by keyword across all feeds."""
        all_deals = await self.get_tech_deals(limit_per_category=20)
        query_words = [w for w in query.lower().split() if len(w) > 2]
        matching = []
        for d in all_deals:
            if query_words and not any(w in (d.title + ' ' + d.description).lower() for w in query_words):
                continue
            matching.append(d)
        return matching[:limit]

    async def _fetch_feed(self, feed_url: str, source: str, limit: int = 15) -> List[Deal]:
        """Fetch and parse an RSS feed."""
        deals = []
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DealBot/1.0; +https://github.com/bfernando)",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                })
                if resp.status_code != 200:
                    console.print(f"  [yellow]HTTP {resp.status_code} for {source}[/yellow]")
                    return deals
                content = resp.text
        except Exception as e:
            console.print(f"  [red]Fetch error for {source}: {e}[/red]")
            return deals

        feed = feedparser.parse(content)
        entries = feed.entries[:limit * 3]  # Fetch extra to filter down

        for entry in entries:
            deal = self._parse_entry(entry, source)
            if deal and len(deals) < limit:
                deals.append(deal)

        return deals

    async def _fetch_bestseller_page(self, page_url: str, category: str, limit: int = 5) -> List[Deal]:
        """Fetch and parse an Amazon Best Sellers page into Deal objects."""
        deals = []
        try:
            resp = requests.get(page_url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            }, timeout=20)
            if resp.status_code != 200:
                console.print(f"  [yellow]HTTP {resp.status_code} for Amazon best sellers {category}[/yellow]")
                return deals
        except Exception as e:
            console.print(f"  [red]Fetch error for Amazon best sellers {category}: {e}[/red]")
            return deals

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("[data-asin]")

        for item in items:
            deal = self._parse_bestseller_item(item, category)
            if deal and len(deals) < limit:
                deals.append(deal)

        return deals

    def _parse_entry(self, entry, source: str) -> Optional[Deal]:
        """Parse a single RSS entry into a Deal."""
        try:
            title = getattr(entry, 'title', '') or ''
            description = ''

            # Try multiple description fields
            for field in ['summary', 'description', 'content']:
                val = getattr(entry, field, None)
                if val:
                    if isinstance(val, list) and val:
                        description = val[0].get('value', '') if isinstance(val[0], dict) else str(val[0])
                    else:
                        description = str(val)
                    break

            # Strip HTML tags from description
            description_clean = re.sub(r'<[^>]+>', ' ', description)
            description_clean = re.sub(r'\s+', ' ', description_clean).strip()

            # Only process tech deals
            if not is_tech_deal(title, description_clean):
                return None

            # Find Amazon URLs in title, description, and link
            link = getattr(entry, 'link', '') or ''
            all_text = f"{title} {description} {link}"
            amazon_urls = extract_amazon_urls(all_text)

            # Also check entry link directly
            if 'amazon.com' in link:
                amazon_urls.insert(0, link)

            asin = None
            for url in amazon_urls:
                asin = extract_asin(url)
                if asin:
                    break

            if not asin:
                return None

            affiliate_url = build_affiliate_url(asin)
            current_price = parse_price(title) or parse_price(description_clean)
            original_price = 0.0
            discount = parse_discount(title) or parse_discount(description_clean)

            # Estimate original price if we have current + discount
            if current_price > 0 and discount > 0:
                original_price = round(current_price / (1 - discount / 100), 2)

            return Deal(
                title=title[:200],
                asin=asin,
                current_price=current_price,
                original_price=original_price,
                discount_percent=discount,
                rating=0.0,
                review_count=0,
                image_url='',
                url=f"https://www.amazon.com/dp/{asin}",
                affiliate_url=affiliate_url,
                source=source,
                description=description_clean[:300],
            )

        except Exception as e:
            return None

    def _parse_bestseller_item(self, item, category: str) -> Optional[Deal]:
        """Parse a bestseller page item into a Deal-like object."""
        try:
            asin = (item.get("data-asin") or "").strip().upper()
            if not asin or not re.match(r"^[A-Z0-9]{10}$", asin):
                return None

            title_node = item.select_one('div[class*="line-clamp"]')
            title = title_node.get_text(" ", strip=True) if title_node else ""
            if not title or not is_tech_deal(title):
                return None

            price_node = (
                item.select_one('span[class*="p13n-sc-price"]')
                or item.select_one(".a-color-price")
            )
            current_price = parse_price(price_node.get_text(" ", strip=True) if price_node else "")
            if current_price <= 0:
                current_price = parse_price(item.get_text(" ", strip=True))
            if current_price <= 0:
                return None

            rating = 0.0
            review_count = 0
            rating_link = item.select_one('[aria-label*="out of 5 stars"]')
            if rating_link:
                aria = rating_link.get("aria-label", "")
                rating_match = re.search(r"([\d.]+)\s+out of 5 stars", aria)
                count_match = re.search(r"([\d,]+)\s+ratings", aria)
                if rating_match:
                    rating = float(rating_match.group(1))
                if count_match:
                    review_count = int(count_match.group(1).replace(",", ""))

            image = item.select_one("img")
            image_url = image.get("src", "") if image else ""
            affiliate_url = build_affiliate_url(asin)

            return Deal(
                title=title[:200],
                asin=asin,
                current_price=current_price,
                original_price=current_price,
                discount_percent=0,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                url=f"https://www.amazon.com/dp/{asin}",
                affiliate_url=affiliate_url,
                is_prime=False,
                is_amazon_shipped=True,
                category=category,
                deal_type="bestseller",
                source=f"amazon-bestsellers-{category}",
                description="Amazon tech bestseller fallback",
            )
        except Exception:
            return None

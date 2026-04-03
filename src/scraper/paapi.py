"""Amazon Creators API scraper - the new API replacing PA-API."""
from typing import List, Optional
from dataclasses import dataclass
from rich.console import Console

console = Console()


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
    is_amazon_shipped: bool = False
    category: str = ""
    deal_type: str = ""


class CreatorsAPIDealScraper:
    """Scrape Amazon deals using the Creators API (replaces PA-API)."""

    def __init__(self, config):
        self.config = config
        self.api = None
        self._init_client()

    def _init_client(self):
        """Initialize Creators API client."""
        try:
            from amazon_creatorsapi import AmazonCreatorsApi

            self.api = AmazonCreatorsApi(
                credential_id=self.config.AMAZON_CREDS_ID,
                credential_secret=self.config.AMAZON_CREDS_SECRET,
                version=self.config.AMAZON_CREDS_VERSION,
                tag=self.config.AMAZON_AFFILIATE_TAG,
                country=self.config.AMAZON_REGION,
            )
            console.print("[green]Amazon Creators API client initialized[/green]")
        except Exception as e:
            console.print(f"[red]Creators API init error: {e}[/red]")

    def search_deals(self, keywords: str, min_discount: int = 20, limit: int = 10) -> List[Deal]:
        """Search for deals using Creators API."""
        if not self.api:
            console.print("[red]Creators API client not initialized[/red]")
            return []

        deals = []
        try:
            result = self.api.search_items(
                keywords=keywords,
                search_index="Electronics",
                item_count=min(limit, 10),
                min_price=int(self.config.PRICE_RANGE_MIN * 100),
                max_price=int(self.config.PRICE_RANGE_MAX * 100),
                min_saving_percent=min_discount,
            )

            if result and hasattr(result, 'items') and result.items:
                for item in result.items:
                    deal = self._item_to_deal(item, keywords)
                    if deal:
                        deals.append(deal)

        except Exception as e:
            console.print(f"[red]Creators API search error: {e}[/red]")

        deals.sort(key=lambda d: d.discount_percent, reverse=True)
        return deals[:limit]

    def search_multiple_categories(self, search_terms: List[str], min_discount: int = 20, limit_per_search: int = 5) -> List[Deal]:
        """Search multiple categories for deals."""
        all_deals = []
        seen_asins = set()

        for term in search_terms:
            console.print(f"[cyan]Creators API searching: {term}[/cyan]")
            deals = self.search_deals(term, min_discount=min_discount, limit=limit_per_search)
            for deal in deals:
                if deal.asin not in seen_asins:
                    all_deals.append(deal)
                    seen_asins.add(deal.asin)
            console.print(f"  Found {len(deals)} deals")

        all_deals.sort(key=lambda d: d.discount_percent, reverse=True)
        return all_deals

    def _item_to_deal(self, item, category: str) -> Optional[Deal]:
        """Convert Creators API item to Deal object."""
        try:
            # Title
            title = ""
            if hasattr(item, 'item_info') and hasattr(item.item_info, 'title'):
                title = item.item_info.title.display_value or ""
            if len(title) > 200:
                title = title[:197] + "..."

            # ASIN
            asin = item.asin or ""

            # Prices
            current_price = 0.0
            original_price = 0.0
            discount_percent = 0

            if hasattr(item, 'offers') and item.offers and item.offers.listings:
                listing = item.offers.listings[0]
                if hasattr(listing, 'price') and listing.price:
                    current_price = listing.price.amount or 0.0
                if hasattr(listing, 'saving_basis') and listing.saving_basis:
                    original_price = listing.saving_basis.amount or 0.0
                if original_price > 0 and current_price > 0:
                    discount_percent = int((1 - current_price / original_price) * 100)

            if original_price == 0 and current_price > 0:
                original_price = round(current_price * 1.3, 2)
                discount_percent = int((1 - current_price / original_price) * 100)

            if current_price < self.config.PRICE_RANGE_MIN or current_price > self.config.PRICE_RANGE_MAX:
                return None

            # Rating
            rating = 0.0
            review_count = 0
            if hasattr(item, 'customer_reviews'):
                if hasattr(item.customer_reviews, 'star_rating') and item.customer_reviews.star_rating:
                    rating = float(item.customer_reviews.star_rating)
                if hasattr(item.customer_reviews, 'count') and item.customer_reviews.count:
                    review_count = item.customer_reviews.count

            # Image
            image_url = ""
            if hasattr(item, 'images') and hasattr(item.images, 'primary') and hasattr(item.images.primary, 'large'):
                image_url = item.images.primary.large.url or ""

            # Prime
            is_prime = False
            if hasattr(item, 'offers') and item.offers and item.offers.listings:
                listing = item.offers.listings[0]
                if hasattr(listing, 'delivery_info'):
                    is_prime = getattr(listing.delivery_info, 'is_prime_eligible', False)

            url = f"https://www.amazon.com/dp/{asin}"
            affiliate_url = f"https://www.amazon.com/dp/{asin}?tag={self.config.AMAZON_AFFILIATE_TAG}"

            return Deal(
                title=title,
                asin=asin,
                current_price=current_price,
                original_price=original_price,
                discount_percent=discount_percent,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                url=url,
                affiliate_url=affiliate_url,
                is_prime=is_prime,
                is_amazon_shipped=True,
                category=category,
                deal_type="creators_api",
            )

        except Exception as e:
            console.print(f"[yellow]Item parse error: {e}[/yellow]")
            return None

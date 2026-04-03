"""Configuration for Amazon Deals Bot."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load shared keys first (Twitter, Amazon, Anthropic, etc.)
_SHARED_ENV = Path.home() / "projects" / ".env.shared"
load_dotenv(_SHARED_ENV)

# Project-specific settings override shared ones
_PROJECT_ENV = Path(__file__).parent.parent / ".env"
load_dotenv(_PROJECT_ENV, override=True)


class Config:
    # Amazon Associates
    AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "thetechbff00-20")
    AMAZON_REGION = os.getenv("AMAZON_REGION", "US")

    # Amazon Creators API (replaces PA-API)
    AMAZON_CREDS_ID = os.getenv("AMAZON_CREDS_ID", "")
    AMAZON_CREDS_SECRET = os.getenv("AMAZON_CREDS_SECRET", "")
    AMAZON_CREDS_VERSION = os.getenv("AMAZON_CREDS_VERSION", "3.1")

    # X/Twitter API
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
    TWITTER_USER_ID = os.getenv("TWITTER_USER_ID", "")

    # Instagram Graph API
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

    # TikTok API
    TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
    TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
    TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

    # YouTube Data API v3 + Analytics
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
    YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
    YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
    YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

    # Deal Settings
    DEAL_CATEGORIES = os.getenv("DEAL_CATEGORIES", "electronics,computers,accessories").split(",")
    MIN_DISCOUNT_PERCENT = int(os.getenv("MIN_DISCOUNT_PERCENT", "20"))
    MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "8"))
    ONLY_AMAZON_SHIPPED = os.getenv("ONLY_AMAZON_SHIPPED", "true").lower() == "true"
    PRICE_RANGE_MIN = float(os.getenv("PRICE_RANGE_MIN", "10"))
    PRICE_RANGE_MAX = float(os.getenv("PRICE_RANGE_MAX", "500"))

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "output"
    CURATED_DEALS_FILE = os.getenv(
        "CURATED_DEALS_FILE",
        str(BASE_DIR / "data" / "openclaw_morning_curated_deals.json"),
    )

    # Amazon domains by region
    AMAZON_DOMAINS = {
        "US": "www.amazon.com",
        "UK": "www.amazon.co.uk",
        "CA": "www.amazon.ca",
        "DE": "www.amazon.de",
    }

    @classmethod
    def get_amazon_domain(cls):
        return cls.AMAZON_DOMAINS.get(cls.AMAZON_REGION, "www.amazon.com")

    @classmethod
    def generate_affiliate_link(cls, asin: str) -> str:
        """Generate Amazon affiliate link from ASIN."""
        domain = cls.get_amazon_domain()
        return f"https://{domain}/dp/{asin}?tag={cls.AMAZON_AFFILIATE_TAG}"


config = Config()

import unittest
from urllib.parse import urlparse

from src.config import config
from src.formatter.tweet import format_deal_thread, format_deal_tweet
from src.scraper.deals import Deal


def sample_deal(**overrides) -> Deal:
    base = Deal(
        title="42% OFF - Sony WH-1000XM5 Wireless Headphones",
        asin="B09XSDMT4F",
        current_price=229.99,
        original_price=399.99,
        discount_percent=42,
        rating=4.7,
        review_count=12034,
        image_url="https://example.com/image.jpg",
        url="https://www.amazon.com/dp/B09XSDMT4F",
        affiliate_url="https://www.amazon.com/dp/B09XSDMT4F?tag=thetechbff00-20",
        is_prime=True,
        is_amazon_shipped=True,
        category="tech",
        deal_type="rss_deal",
        source="fixture",
        description="Fixture deal",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TweetFormatterTests(unittest.TestCase):
    def test_single_tweet_layout_has_disclosure_before_url(self) -> None:
        text = format_deal_tweet(sample_deal())
        lines = text.splitlines()

        self.assertEqual(lines[0], "42% OFF - Sony WH-1000XM5 Wireless Headphones")
        self.assertEqual(lines[1], "Now $229.99 (was $399.99)")
        self.assertEqual(lines[2], "#ad #affiliate")
        self.assertTrue(lines[3].startswith("https://www.amazon.com/dp/B09XSDMT4F?tag="))
        self.assertEqual(lines[4], "#AmazonDeals #TechDeals")

    def test_title_normalization_drops_duplicate_off_prefix(self) -> None:
        text = format_deal_tweet(sample_deal(title="42% OFF - 42% OFF - Anker USB-C Charger"))
        lines = text.splitlines()
        self.assertEqual(lines[0], "42% OFF - Anker USB-C Charger")

    def test_invalid_affiliate_url_is_canonicalized_from_asin(self) -> None:
        text = format_deal_tweet(sample_deal(affiliate_url="not-a-valid-url"))
        lines = text.splitlines()
        self.assertEqual(lines[3], config.generate_affiliate_link("B09XSDMT4F"))
        parsed = urlparse(lines[3])
        self.assertEqual(parsed.scheme, "https")
        self.assertTrue(parsed.netloc)
        self.assertTrue(parsed.path.startswith("/dp/"))

    def test_thread_deal_tweets_include_disclosure_for_each_amazon_link(self) -> None:
        deals = [
            sample_deal(title="Deal A", asin="B09XSDMT4F"),
            sample_deal(title="Deal B", asin="B09XSDMT4G", affiliate_url="bad"),
        ]
        tweets = format_deal_thread(deals)

        self.assertGreaterEqual(len(tweets), 3)
        self.assertIn("#ad #affiliate", tweets[0])

        deal_tweet_1 = tweets[1].splitlines()
        deal_tweet_2 = tweets[2].splitlines()

        self.assertEqual(deal_tweet_1[2], "#ad #affiliate")
        self.assertTrue(deal_tweet_1[3].startswith("https://www.amazon.com/dp/"))
        self.assertEqual(deal_tweet_2[2], "#ad #affiliate")
        self.assertTrue(deal_tweet_2[3].startswith("https://www.amazon.com/dp/"))


if __name__ == "__main__":
    unittest.main()

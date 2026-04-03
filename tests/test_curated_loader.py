import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from src.config import config
from src.scraper.deals import AmazonDealScraper


class CuratedLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_curated_file = config.CURATED_DEALS_FILE

    def tearDown(self) -> None:
        config.CURATED_DEALS_FILE = self.original_curated_file

    def test_loads_json_curated_deals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            curated_path = Path(tmp) / "curated.json"
            curated_path.write_text(
                json.dumps(
                    {
                        "deals": [
                            {
                                "title": "Noise Cancelling Headphones",
                                "asin": "B09XS7JWHH",
                                "current_price": 199.99,
                                "original_price": 249.99,
                                "discount_percent": 20,
                                "source": "openclaw-brief",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config.CURATED_DEALS_FILE = str(curated_path)
            scraper = AmazonDealScraper()
            deals = asyncio.run(scraper.get_curated_deals(limit=5))

        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].asin, "B09XS7JWHH")
        self.assertEqual(deals[0].current_price, 199.99)
        self.assertEqual(deals[0].source, "openclaw-brief")

    def test_loads_csv_and_skips_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            curated_path = Path(tmp) / "curated.csv"
            curated_path.write_text(
                "title,asin,current_price,source\n"
                "Valid Deal,B09XSDMT4F,129.99,openclaw-csv\n"
                "Missing Price,B09XSDMT4G,,openclaw-csv\n"
                "Bad ASIN,INVALID,59.99,openclaw-csv\n",
                encoding="utf-8",
            )
            config.CURATED_DEALS_FILE = str(curated_path)
            scraper = AmazonDealScraper()
            deals = asyncio.run(scraper.get_curated_deals(limit=10))

        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].asin, "B09XSDMT4F")
        self.assertEqual(deals[0].source, "openclaw-csv")


if __name__ == "__main__":
    unittest.main()

import asyncio
from src.scraper.deals import AmazonDealScraper
from dotenv import load_dotenv
load_dotenv()

async def main():
    scraper = AmazonDealScraper()
    queries = ['electronics', 'tech deals', 'laptop deals']
    for q in queries:
        print(f'Searching for: {q}')
        deals = await scraper.search_deals(q, limit=5)
        print(f'  Found {len(deals)} deals')
        for d in deals:
            print(f'    {d.title[:70]} - ${d.current_price} → {d.discount_percent}% off')
        print()

asyncio.run(main())

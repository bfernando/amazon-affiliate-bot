# Amazon Deals to Twitter/X Bot

Automatically finds tech products and affiliate opportunities from deal feeds, then posts to Twitter/X.

Current behavior:
- Tries OpenClaw morning curated list first.
- Falls back to fresh discounted tech deals if curated list is missing/empty/exhausted.
- If no new discounted deals are available, falls back to Amazon tech best sellers.
- Uses Amazon affiliate links in every post.

## Setup

### Prerequisites
1. Ensure you have Python 3.8+ installed
2. Install [Git](https://git-scm.com/) if not already installed

### Installation
```bash
# Clone the repository
git clone https://github.com/bfernando/amazon-affiliate-bot.git
cd amazon-affiliate-bot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
1. Copy the example configuration file:
```bash
cp .env.example .env
```
2. Edit `.env` and fill in all required credentials:
   - **AMAZON_AFFILIATE_TAG** (your Amazon Associates ID)
   - **TWITTER_API_KEY**, **TWITTER_API_SECRET**, **TWITTER_ACCESS_TOKEN**, **TWITTER_ACCESS_SECRET**, **TWITTER_BEARER_TOKEN**
3. Optional configuration:
   - **MIN_DISCOUNT_PERCENT** (default: 20)
   - **ONLY_AMAZON_SHIPPED** (true/false)
   - **PRICE_RANGE_MIN/MAX** (e.g., 10/500)
   - **DEAL_CATEGORIES** (comma-separated list)
   - **CURATED_DEALS_FILE** (default: `data/openclaw_morning_curated_deals.json`)

### OpenClaw Morning Handoff Format
The curated handoff file supports `.json` or `.csv`.

JSON (preferred):
```json
{
  "deals": [
    {
      "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
      "asin": "B09XS7JWHH",
      "current_price": 278.00,
      "original_price": 399.99,
      "discount_percent": 30,
      "affiliate_url": "https://www.amazon.com/dp/B09XS7JWHH?tag=twitterxthetechbff-20",
      "source": "openclaw-morning-brief-2026-04-03"
    }
  ]
}
```

CSV columns (minimum required): `title,asin,current_price`
- Optional: `original_price,discount_percent,affiliate_url,amazon_url,source,description,rating,review_count,is_prime,is_amazon_shipped,category,image_url`

## Usage

### Basic Commands
```bash
# Preview deals without posting
python main.py

# Search for specific products
python main.py --search "airpods"

# Post the best deal to Twitter
python main.py --post --mode best

# Post as a thread (up to 10 deals)
python main.py --post --mode thread

# Verify Twitter credentials
python main.py --verify

# Find more deals
python main.py --limit 20
```

### News Bot X
News/article posting has been moved out of this repository into its own standalone project folder/repo:
`C:\Projects\news-bot-x`.

## Scheduling

This project should run exactly one scheduler backend (Windows Task Scheduler, `launchd`, or cron) to avoid duplicate posts.
Morning workflow:
1. Generate/update the curated file before the first scheduled run.
2. Keep hourly schedule unchanged; each run consumes curated deals first.
3. If curated entries are exhausted or already posted, bot automatically falls back to RSS/Twitter, then bestsellers.

Useful checks:

```bash
# Windows Task Scheduler (PowerShell)
Get-ScheduledTask | Where-Object { $_.TaskName -match 'AmazonDealsBotHourly' }

# launchd (macOS)
launchctl list | rg 'twitterdealsbot'

# cron (macOS/Linux)
crontab -l
```

## Posting Logic

Per run, the bot does this:

1. Loads OpenClaw curated candidates (`CURATED_DEALS_FILE`) and validates required affiliate fields.
2. Skips ASINs already present in `posted_deals.txt`.
3. If curated lane has no usable candidates, fetches RSS (Reddit/Slickdeals/DealNews) and Twitter deal-account sources.
4. If no fresh discounted deal is available, fetches Amazon tech best sellers as fallback.
5. Posts the best available candidate (if any).

If you see "not posting," the most common cause is that all eligible ASINs have already been posted and deduped.

### Advanced Options
- **--limit N**: Show N deals (default: 10)
- **--category C**: Filter by category (e.g., electronics, books)
- **--price MIN MAX**: Price range filter
- **--discount MIN MAX**: Minimum discount percentage

## Troubleshooting
- **No posts appearing?** Check `bot.log` for "already posted" and fallback messages.
- **No deals found?** Check source availability and your affiliate/tag settings.
- **Twitter API errors?** Verify your Twitter developer account is active
- **Missing dependencies?** Run `pip install -r requirements.txt` again

## Project Structure

```
amazon-affiliate-bot/
├── main.py                    # Entry point
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py              # Configuration
│   ├── scraper/
│   │   └── deals.py           # Amazon deal scraping
│   ├── formatter/
│   │   └── tweet.py           # Tweet formatting
│   └── poster/
│       └── twitter.py         # Twitter API posting
├── data/
│   └── openclaw_morning_curated_deals.json  # Curated handoff template
└── output/                    # Saved deal data
```

## FTC Compliance

All tweets include `#ad #affiliate` disclosure as required by FTC guidelines for affiliate marketing.

## Support
For issues or feature requests, please open an issue on [GitHub](https://github.com/bfernando/amazon-affiliate-bot).


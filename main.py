#!/usr/bin/env python3
"""
Amazon Deals to Twitter/X Bot

Usage:
  python main.py                      # Find deals and print formatted tweets
  python main.py --post               # Find deals and post to Twitter
  python main.py --post --mode best   # Post only the single best deal
  python main.py --post --mode thread # Post as a thread (up to 10 deals)
  python main.py --search "airpods"   # Search for specific product deals
  python main.py --verify             # Verify Twitter credentials
  python main.py --dry-run            # Preview tweets without posting
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Prevent Windows cp1252 console crashes when Rich prints Unicode characters.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.config import config
from src.scraper.deals import AmazonDealScraper
from src.formatter.tweet import format_deal_tweet, format_deal_thread, format_single_best_deal
from src.poster.twitter import TwitterPoster
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

POSTED_FILE = Path(__file__).parent / "posted_deals.txt"
LOG_FILE = Path(__file__).parent / "bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE)],
)
log = logging.getLogger(__name__)


def load_posted_asins() -> set:
    if not POSTED_FILE.exists():
        return set()
    asins = set()
    for line in POSTED_FILE.read_text().splitlines():
        line = line.strip()
        if line:
            asins.add(line.split("|")[0])
    return asins


def mark_posted(asin: str):
    ts = datetime.now(timezone.utc).isoformat()
    with open(POSTED_FILE, "a") as f:
        f.write(f"{asin}|{ts}\n")


def cleanup_posted_file():
    """Remove entries older than 90 days from posted_deals.txt."""
    if not POSTED_FILE.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    kept = []
    for line in POSTED_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 1)
        if len(parts) == 2:
            try:
                ts = datetime.fromisoformat(parts[1])
                if ts >= cutoff:
                    kept.append(line)
                continue
            except ValueError:
                pass
        kept.append(line)  # keep lines without timestamps
    POSTED_FILE.write_text("\n".join(kept) + ("\n" if kept else ""))


def get_twitter_poster() -> TwitterPoster:
    """Initialize Twitter poster from config."""
    return TwitterPoster(
        api_key=config.TWITTER_API_KEY,
        api_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_secret=config.TWITTER_ACCESS_SECRET,
        bearer_token=config.TWITTER_BEARER_TOKEN,
    )


def display_deals(deals):
    """Display deals in a nice table."""
    table = Table(title="Tech Deals Found")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("Price", style="green")
    table.add_column("Was", style="red")
    table.add_column("Off", style="yellow")
    table.add_column("Rating", style="magenta")

    for i, deal in enumerate(deals, 1):
        table.add_row(
            str(i),
            deal.title[:50],
            f"${deal.current_price:,.2f}",
            f"${deal.original_price:,.2f}" if deal.original_price > 0 else "-",
            f"{deal.discount_percent}%",
            f"⭐ {deal.rating}" if deal.rating > 0 else "-",
        )

    console.print(table)


async def run(args):
    """Main execution."""
    scraper = AmazonDealScraper()
    fallback_to_bestsellers = False

    # Verify mode
    if args.verify:
        poster = get_twitter_poster()
        poster.verify_credentials()
        return

    # Search or scrape
    if args.search:
        console.print(Panel(f"[bold cyan]Searching deals for: {args.search}[/bold cyan]"))
        deals = await scraper.search_deals(args.search, limit=args.limit)
    else:
        console.print(Panel("[bold cyan]🔍 Scanning for tech deals...[/bold cyan]"))
        deals = await scraper.get_tech_deals(limit_per_category=args.limit)

    if not deals:
        if args.search:
            console.print("[yellow]No deals found matching criteria[/yellow]")
            return
        fallback_to_bestsellers = True
        console.print("[yellow]No fresh discounted deals found. Falling back to Amazon tech best sellers.[/yellow]")
        deals = await scraper.get_bestseller_deals(limit_per_category=max(3, min(args.limit, 5)))
        if not deals:
            console.print("[yellow]No best seller fallback items found[/yellow]")
            return

    # Deduplicate against already-posted ASINs
    cleanup_posted_file()
    posted_asins = load_posted_asins()
    original_count = len(deals)
    deals = [d for d in deals if d.asin not in posted_asins]
    if len(deals) < original_count:
        console.print(f"[dim]Skipped {original_count - len(deals)} already-posted deal(s)[/dim]")

    if not deals:
        if args.search:
            console.print("[yellow]All found deals have already been posted[/yellow]")
            return
        fallback_to_bestsellers = True
        console.print("[yellow]All fresh deals were already posted. Falling back to Amazon tech best sellers.[/yellow]")
        deals = await scraper.get_bestseller_deals(limit_per_category=max(3, min(args.limit, 5)))
        deals = [d for d in deals if d.asin not in posted_asins]
        if not deals:
            console.print("[yellow]All fallback best sellers have already been posted[/yellow]")
            return

    # Display deals
    display_deals(deals)
    if fallback_to_bestsellers:
        console.print("[dim]Posting bestseller fallback because no new discounted affiliate deals were available.[/dim]")

    # Format tweets
    if args.mode == "best":
        best_deal = deals[0]
        tweet_text = format_single_best_deal(best_deal)
        console.print(Panel(tweet_text, title="[bold]Tweet Preview[/bold]"))

        if args.dry_run:
            console.print(f"[yellow][DRY RUN] Would have posted:[/yellow]\n{tweet_text}")
            log.info("DRY RUN - no tweet sent")
        elif args.post:
            poster = get_twitter_poster()
            poster.post_tweet(tweet_text)
            mark_posted(best_deal.asin)

    elif args.mode == "thread":
        thread_tweets = format_deal_thread(deals[:10])
        console.print(f"\n[bold]Thread Preview ({len(thread_tweets)} tweets):[/bold]")
        for i, tweet in enumerate(thread_tweets):
            console.print(Panel(tweet, title=f"[bold]Tweet {i+1}/{len(thread_tweets)}[/bold]"))

        if args.dry_run:
            console.print(f"[yellow][DRY RUN] Would have posted {len(thread_tweets)} thread tweets[/yellow]")
            log.info("DRY RUN - no tweet sent")
        elif args.post:
            poster = get_twitter_poster()
            poster.post_thread(thread_tweets)
            for deal in deals[:10]:
                mark_posted(deal.asin)

    else:
        # Just show previews
        for i, deal in enumerate(deals[:5], 1):
            console.print(f"\n[bold]Deal {i}:[/bold]")
            console.print(Panel(format_deal_tweet(deal)))

        if args.dry_run:
            console.print("[yellow][DRY RUN] Would have posted (use --mode best or --mode thread)[/yellow]")
            log.info("DRY RUN - no tweet sent")
        elif args.post:
            console.print("[yellow]Specify --mode best or --mode thread to post[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Amazon Deals to Twitter/X Bot")
    parser.add_argument("--post", action="store_true", help="Actually post to Twitter (default is preview)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Preview tweet without posting (skips Twitter API entirely)")
    parser.add_argument("--mode", choices=["best", "thread"], default="best",
                        help="Post mode: single best deal or thread of deals")
    parser.add_argument("--search", "-s", type=str, help="Search for specific product deals")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max deals to find")
    parser.add_argument("--verify", action="store_true", help="Verify Twitter API credentials")

    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()

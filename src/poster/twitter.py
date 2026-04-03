"""Twitter/X posting via API v2 (pay-per-use)."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from rich.console import Console

console = Console()

LOG_FILE = Path(__file__).parent.parent.parent / "bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE)],
)
log = logging.getLogger(__name__)

RATE_LIMIT_WAIT_SECONDS = 15 * 60  # 15 minutes


@dataclass
class Tweet:
    id: str
    text: str
    url: str
    created_at: str


class TwitterPoster:
    """Post tweets via Twitter API v2."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str,
        bearer_token: str = "",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_secret = access_secret
        self.bearer_token = bearer_token
        self.auth = None
        self._init_client()

    def _init_client(self):
        """Initialize OAuth 1.0a auth for v2 API."""
        try:
            from requests_oauthlib import OAuth1
            self.auth = OAuth1(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_secret,
            )
            console.print("[green]Twitter v2 API client initialized[/green]")
        except ImportError:
            console.print("[red]requests-oauthlib not installed[/red]")
        except Exception as e:
            console.print(f"[red]Twitter client error: {e}[/red]")

    def _do_post(self, payload: dict):
        """Make a single POST to the tweets endpoint. Returns the requests.Response."""
        import requests
        return requests.post(
            "https://api.twitter.com/2/tweets",
            json=payload,
            auth=self.auth,
        )

    def _handle_response(self, r, attempt: int) -> Optional[Tweet]:
        """Parse a tweet response, handling 429/403. Returns Tweet or None."""
        import requests

        if r.status_code == 201:
            data = r.json()["data"]
            tweet = Tweet(
                id=data["id"],
                text=data["text"],
                url=f"https://twitter.com/i/status/{data['id']}",
                created_at="",
            )
            console.print(f"[green]Tweet posted: {tweet.url}[/green]")
            return tweet

        if r.status_code == 429:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"Rate limit hit (429) at {ts} — attempt {attempt}"
            log.warning(msg)
            console.print(f"[yellow]{msg}[/yellow]")
            return "rate_limited"

        if r.status_code == 403:
            msg = f"Forbidden (403): {r.text[:200]} — likely duplicate tweet or insufficient permissions"
            log.error(msg)
            console.print(f"[red]{msg}[/red]")
            return None

        console.print(f"[red]Tweet error {r.status_code}: {r.text[:200]}[/red]")
        return None

    def post_tweet(self, text: str) -> Optional[Tweet]:
        """Post a single tweet via v2 API. Retries once after 15 min on rate limit."""
        if not self.auth:
            console.print("[red]Twitter client not initialized[/red]")
            return None

        try:
            if len(text) > 280:
                text = text[:277] + "..."

            payload = {"text": text}
            r = self._do_post(payload)
            result = self._handle_response(r, attempt=1)

            if result == "rate_limited":
                console.print(f"[yellow]Waiting {RATE_LIMIT_WAIT_SECONDS // 60} minutes before retry...[/yellow]")
                time.sleep(RATE_LIMIT_WAIT_SECONDS)
                r = self._do_post(payload)
                result = self._handle_response(r, attempt=2)
                if result == "rate_limited":
                    msg = "Still rate limited after retry — giving up gracefully"
                    log.error(msg)
                    console.print(f"[red]{msg}[/red]")
                    return None

            return result if result != "rate_limited" else None

        except Exception as e:
            console.print(f"[red]Tweet error: {e}[/red]")
            return None

    def post_thread(self, tweets: List[str]) -> List[Tweet]:
        """Post a thread of tweets via v2 API."""
        if not self.auth:
            console.print("[red]Twitter client not initialized[/red]")
            return []

        posted = []
        previous_tweet_id = None

        for i, text in enumerate(tweets):
            try:
                if len(text) > 280:
                    text = text[:277] + "..."

                payload = {"text": text}
                if previous_tweet_id:
                    payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}

                r = self._do_post(payload)
                result = self._handle_response(r, attempt=1)

                if result == "rate_limited":
                    console.print(f"[yellow]Waiting {RATE_LIMIT_WAIT_SECONDS // 60} minutes before retry...[/yellow]")
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    r = self._do_post(payload)
                    result = self._handle_response(r, attempt=2)
                    if result == "rate_limited":
                        msg = f"Still rate limited on thread tweet {i+1} — stopping thread"
                        log.error(msg)
                        console.print(f"[red]{msg}[/red]")
                        break

                if result is None or result == "rate_limited":
                    console.print(f"[red]Thread tweet {i+1} failed — stopping thread[/red]")
                    break

                posted.append(result)
                previous_tweet_id = result.id
                console.print(f"[green]Thread tweet {i+1}/{len(tweets)} posted[/green]")

            except Exception as e:
                console.print(f"[red]Thread tweet {i+1} error: {e}[/red]")
                break

        return posted

    def post_tweet_with_image(self, text: str, image_path: Path) -> Optional[Tweet]:
        """Post a tweet with an image via v2 API (needs media upload through v1.1)."""
        import requests

        if not self.auth:
            console.print("[red]Twitter client not initialized[/red]")
            return None

        try:
            import tweepy

            # v2 API doesn't support media upload yet — use v1.1 for upload
            auth_v1 = tweepy.OAuth1UserHandler(
                self.api_key, self.api_secret,
                self.access_token, self.access_secret,
            )
            api_v1 = tweepy.API(auth_v1)
            media = api_v1.media_upload(filename=str(image_path))
            media_id = str(media.media_id)

            # Post via v2 with media
            if len(text) > 280:
                text = text[:277] + "..."

            r = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": text, "media": {"media_ids": [media_id]}},
                auth=self.auth,
            )

            if r.status_code == 201:
                data = r.json()["data"]
                tweet = Tweet(
                    id=data["id"],
                    text=data["text"],
                    url=f"https://twitter.com/i/status/{data['id']}",
                    created_at="",
                )
                console.print(f"[green]Tweet with image posted: {tweet.url}[/green]")
                return tweet
            else:
                console.print(f"[red]Image tweet error {r.status_code}: {r.text[:200]}[/red]")
                return None

        except Exception as e:
            console.print(f"[red]Tweet with image error: {e}[/red]")
            return None

    def verify_credentials(self) -> bool:
        """Verify the Twitter API credentials work."""
        import requests

        if not self.auth:
            return False

        try:
            r = requests.get("https://api.twitter.com/2/users/me", auth=self.auth)
            if r.status_code == 200:
                data = r.json()["data"]
                console.print(f"[green]Authenticated as: @{data['username']}[/green]")
                return True
            else:
                console.print(f"[red]Auth verification failed: {r.status_code}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Auth verification failed: {e}[/red]")
            return False

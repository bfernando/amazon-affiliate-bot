"""Instagram posting via Meta Graph API."""
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from rich.console import Console

console = Console()

LOG_FILE = Path(__file__).parent.parent.parent / "bot.log"
log = logging.getLogger(__name__)


@dataclass
class InstagramPost:
    id: str
    caption: str
    url: str


class InstagramPoster:
    """Post images + captions to Instagram via Meta Graph API."""

    BASE_URL = "https://graph.instagram.com/v21.0"

    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        self.account_id = account_id

    def _post(self, endpoint: str, data: dict) -> Optional[dict]:
        """Make a POST request to the Graph API."""
        import requests
        url = f"{self.BASE_URL}/{endpoint}"
        data["access_token"] = self.access_token
        try:
            r = requests.post(url, data=data, timeout=30)
            if r.status_code == 200:
                return r.json()
            else:
                console.print(f"[red]Instagram API error {r.status_code}: {r.text[:300]}[/red]")
                log.error(f"Instagram API error {r.status_code}: {r.text[:300]}")
                return None
        except Exception as e:
            console.print(f"[red]Instagram request failed: {e}[/red]")
            log.error(f"Instagram request failed: {e}")
            return None

    def create_media_container(self, image_url: str, caption: str) -> Optional[str]:
        """Step 1: Create a media container. Returns container ID."""
        console.print("[cyan]Creating Instagram media container...[/cyan]")
        result = self._post(
            f"{self.account_id}/media",
            {"image_url": image_url, "caption": caption},
        )
        if result and "id" in result:
            container_id = result["id"]
            console.print(f"[green]Container created: {container_id}[/green]")
            return container_id
        return None

    def publish_container(self, container_id: str) -> Optional[InstagramPost]:
        """Step 2: Publish a media container. Returns the published post."""
        console.print("[cyan]Publishing Instagram post...[/cyan]")
        result = self._post(
            f"{self.account_id}/media_publish",
            {"creation_id": container_id},
        )
        if result and "id" in result:
            post_id = result["id"]
            post_url = f"https://www.instagram.com/p/{post_id}/"
            console.print(f"[green]Instagram post published! ID: {post_id}[/green]")
            log.info(f"Instagram post published: {post_id}")
            return InstagramPost(id=post_id, caption="", url=post_url)
        return None

    def post_image(self, image_url: str, caption: str) -> Optional[InstagramPost]:
        """Full flow: create container, wait briefly, then publish."""
        # Step 1: create container
        container_id = self.create_media_container(image_url, caption)
        if not container_id:
            console.print("[red]Failed to create media container[/red]")
            return None

        # Brief wait — Meta recommends checking status before publishing
        time.sleep(3)

        # Step 2: publish
        post = self.publish_container(container_id)
        if not post:
            console.print("[red]Failed to publish Instagram post[/red]")
            return None

        return post

    def verify_credentials(self) -> bool:
        """Check the token and account ID are working."""
        import requests
        url = f"{self.BASE_URL}/{self.account_id}"
        params = {
            "fields": "id,username",
            "access_token": self.access_token,
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                console.print(f"[green]Instagram auth OK — account: @{data.get('username', data.get('id'))}[/green]")
                return True
            else:
                console.print(f"[red]Instagram auth failed {r.status_code}: {r.text[:200]}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]Instagram auth check failed: {e}[/red]")
            return False

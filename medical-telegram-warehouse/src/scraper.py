"""
Task 1 — Telegram Data Scraper
Scrapes messages and images from public Telegram channels and stores
them in a partitioned data lake structure.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.logger import scraper_logger as log


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _message_dir(date: datetime) -> Path:
    """Return partitioned output path for a given date."""
    day = date.strftime("%Y-%m-%d")
    path = settings.messages_dir / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def _image_dir(channel: str) -> Path:
    path = settings.images_dir / channel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_message(msg, channel_name: str) -> dict:
    """Convert a Telethon Message object to a plain dict."""
    has_media = msg.media is not None
    is_photo = isinstance(msg.media, MessageMediaPhoto)
    return {
        "message_id": msg.id,
        "channel_name": channel_name,
        "message_date": msg.date.isoformat() if msg.date else None,
        "message_text": msg.text or "",
        "has_media": has_media,
        "is_photo": is_photo,
        "image_path": None,  # filled in after download
        "views": getattr(msg, "views", 0) or 0,
        "forwards": getattr(msg, "forwards", 0) or 0,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

class TelegramScraper:
    def __init__(self, limit_per_channel: int = 200):
        self.client = TelegramClient(
            settings.telegram_session_name,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        self.limit = limit_per_channel

    async def _download_image(self, msg, channel: str) -> str | None:
        """Download photo attached to a message; return relative path or None."""
        if not isinstance(msg.media, MessageMediaPhoto):
            return None
        out = _image_dir(channel) / f"{msg.id}.jpg"
        try:
            await self.client.download_media(msg, file=str(out))
            log.debug(f"Downloaded image → {out}")
            return str(out)
        except Exception as exc:
            log.warning(f"Image download failed for {channel}/{msg.id}: {exc}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    async def scrape_channel(self, channel: str) -> list[dict]:
        """Scrape up to self.limit messages from a single channel."""
        log.info(f"Scraping channel: {channel} (limit={self.limit})")
        records: list[dict] = []
        try:
            entity = await self.client.get_entity(channel)
            async for msg in self.client.iter_messages(entity, limit=self.limit):
                record = _serialize_message(msg, channel)
                if record["is_photo"]:
                    path = await self._download_image(msg, channel)
                    record["image_path"] = path
                records.append(record)
        except Exception as exc:
            log.error(f"Failed to scrape {channel}: {exc}")
            raise
        log.info(f"  → {len(records)} messages collected from {channel}")
        return records

    def _save_records(self, channel: str, records: list[dict]) -> Path:
        """Persist records as a partitioned JSON file (one per channel per run date)."""
        today = datetime.now(timezone.utc)
        out_dir = _message_dir(today)
        out_file = out_dir / f"{channel}.json"
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)
        log.info(f"Saved {len(records)} records → {out_file}")
        return out_file

    async def run(self) -> dict[str, int]:
        """Connect, scrape all configured channels, disconnect."""
        summary: dict[str, int] = {}
        async with self.client:
            await self.client.start(phone=settings.telegram_phone)
            log.info("Telegram client connected")
            for channel in settings.telegram_channels:
                try:
                    records = await self.scrape_channel(channel)
                    self._save_records(channel, records)
                    summary[channel] = len(records)
                except Exception as exc:
                    log.error(f"Skipping {channel} after retries: {exc}")
                    summary[channel] = 0
        log.info(f"Scraping complete. Summary: {summary}")
        return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    scraper = TelegramScraper(limit_per_channel=200)
    asyncio.run(scraper.run())


if __name__ == "__main__":
    main()

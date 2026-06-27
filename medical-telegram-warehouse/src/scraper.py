"""
Task 1 — Telegram Data Scraper
================================
Scrapes messages and images from public Telegram channels and stores them in
a partitioned data lake on the local filesystem.

Data lake layout (created automatically on first run):
    data/raw/telegram_messages/YYYY-MM-DD/{channel_name}.json
    data/raw/images/{channel_name}/{message_id}.jpg
    logs/scraper.log

All credentials (API ID, hash, phone) are read from environment variables
via src.config.settings — never hard-coded here.

Usage:
    python -m src.scraper                # scrape live Telegram channels
    python scripts/generate_sample_data.py  # generate sample data (no API needed)
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


# ── Directory helpers ──────────────────────────────────────────────────────────

def _message_partition_dir(date: datetime) -> Path:
    """
    Return the partitioned output directory for a given scrape date.
    Creates: data/raw/telegram_messages/YYYY-MM-DD/
    """
    day = date.strftime("%Y-%m-%d")
    path = settings.messages_dir / day
    path.mkdir(parents=True, exist_ok=True)
    log.debug(f"Message partition dir: {path}")
    return path


def _image_channel_dir(channel: str) -> Path:
    """
    Return the image storage directory for a channel.
    Creates: data/raw/images/{channel_name}/
    """
    path = settings.images_dir / channel
    path.mkdir(parents=True, exist_ok=True)
    log.debug(f"Image dir for {channel}: {path}")
    return path


# ── Message serialisation ──────────────────────────────────────────────────────

def _serialize_message(msg, channel_name: str) -> dict:
    """
    Convert a Telethon Message object to a plain dict with all required fields.

    Extracted fields:
        message_id    — Telegram message ID (unique within a channel)
        channel_name  — Telegram channel handle
        message_date  — UTC ISO-8601 timestamp of the message
        message_text  — Full text content (empty string if None)
        has_media     — True if any media is attached
        is_photo      — True if media is a photo (downloadable)
        image_path    — Set after image download (None initially)
        views         — View count (0 if not available)
        forwards      — Forward count (0 if not available)
        scraped_at    — UTC timestamp of when this record was collected
    """
    has_media = msg.media is not None
    is_photo  = isinstance(msg.media, MessageMediaPhoto)

    return {
        "message_id":   msg.id,
        "channel_name": channel_name,
        "message_date": msg.date.isoformat() if msg.date else None,
        "message_text": msg.text or "",
        "has_media":    has_media,
        "is_photo":     is_photo,
        "image_path":   None,                               # filled after download
        "views":        getattr(msg, "views",    0) or 0,
        "forwards":     getattr(msg, "forwards", 0) or 0,
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
    }


# ── Main scraper class ─────────────────────────────────────────────────────────

class TelegramScraper:
    """
    Scrapes messages and images from a list of public Telegram channels.

    Credentials are read from settings (env vars):
        TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
    """

    def __init__(self, limit_per_channel: int = 200):
        self.client = TelegramClient(
            settings.telegram_session_name,  # session name, from env
            settings.telegram_api_id,        # TELEGRAM_API_ID env var
            settings.telegram_api_hash,      # TELEGRAM_API_HASH env var
        )
        self.limit = limit_per_channel
        log.info(
            f"TelegramScraper initialised | "
            f"channels={len(settings.telegram_channels)} | "
            f"limit_per_channel={limit_per_channel}"
        )

    async def _download_image(self, msg, channel: str) -> str | None:
        """
        Download a photo attached to a message.
        Saves to: data/raw/images/{channel}/{message_id}.jpg
        Returns the saved path as a string, or None on failure.
        """
        if not isinstance(msg.media, MessageMediaPhoto):
            return None

        out_path = _image_channel_dir(channel) / f"{msg.id}.jpg"
        try:
            await self.client.download_media(msg, file=str(out_path))
            log.debug(f"Image saved → {out_path}")
            return str(out_path)
        except Exception as exc:
            log.warning(f"Image download failed [{channel}/{msg.id}]: {exc}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    async def scrape_channel(self, channel: str) -> list[dict]:
        """
        Scrape up to self.limit messages from a single channel.
        Retries up to 3 times with exponential back-off on network errors.
        Logs progress and errors to logs/scraper.log.
        """
        log.info(f"[{channel}] Starting scrape (limit={self.limit})")
        records: list[dict] = []

        try:
            entity = await self.client.get_entity(channel)
            async for msg in self.client.iter_messages(entity, limit=self.limit):
                record = _serialize_message(msg, channel)

                # Download photo if present and update image_path in the record
                if record["is_photo"]:
                    path = await self._download_image(msg, channel)
                    record["image_path"] = path
                    if path:
                        log.debug(f"[{channel}] Photo: {path}")

                records.append(record)

        except Exception as exc:
            log.error(f"[{channel}] Scrape failed: {exc}")
            raise

        log.info(f"[{channel}] Collected {len(records)} messages")
        return records

    def _save_to_data_lake(self, channel: str, records: list[dict]) -> Path:
        """
        Persist records as a partitioned JSON file.
        Output: data/raw/telegram_messages/YYYY-MM-DD/{channel}.json
        Overwrites existing file for the same channel+date (idempotent).
        """
        today    = datetime.now(timezone.utc)
        out_dir  = _message_partition_dir(today)
        out_file = out_dir / f"{channel}.json"

        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)

        log.info(f"[{channel}] Saved {len(records)} records → {out_file}")
        return out_file

    async def run(self) -> dict[str, int]:
        """
        Connect to Telegram, scrape all configured channels, disconnect.
        Returns a summary dict: {channel_name: message_count}.
        """
        summary: dict[str, int] = {}

        log.info("Connecting to Telegram...")
        async with self.client:
            await self.client.start(phone=settings.telegram_phone)
            log.info("Telegram client authenticated")

            for channel in settings.telegram_channels:
                try:
                    records = await self.scrape_channel(channel)
                    self._save_to_data_lake(channel, records)
                    summary[channel] = len(records)
                except Exception as exc:
                    log.error(f"[{channel}] Skipping after all retries: {exc}")
                    summary[channel] = 0

        log.info(f"Scraping complete. Summary: {summary}")
        return summary


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the scraper from the command line: python -m src.scraper"""
    log.info("=" * 60)
    log.info("Medical Telegram Scraper — Task 1")
    log.info(f"Channels: {settings.telegram_channels}")
    log.info(f"Data lake: {settings.messages_dir.resolve()}")
    log.info(f"Images:    {settings.images_dir.resolve()}")
    log.info(f"Logs:      {settings.logs_dir.resolve()}")
    log.info("=" * 60)
    scraper = TelegramScraper(limit_per_channel=200)
    asyncio.run(scraper.run())


if __name__ == "__main__":
    main()

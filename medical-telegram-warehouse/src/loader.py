"""
Task 2 (Load step) — Raw JSON → PostgreSQL
Reads all JSON files from the data lake and inserts them into the
raw.telegram_messages table in PostgreSQL.
"""

import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from src.config import settings
from src.logger import loader_logger as log

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS raw;"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw.telegram_messages (
    id              SERIAL PRIMARY KEY,
    message_id      BIGINT,
    channel_name    TEXT,
    message_date    TIMESTAMPTZ,
    message_text    TEXT,
    has_media       BOOLEAN,
    is_photo        BOOLEAN,
    image_path      TEXT,
    views           INTEGER,
    forwards        INTEGER,
    scraped_at      TIMESTAMPTZ,
    loaded_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (message_id, channel_name)
);
"""

INSERT_SQL = """
INSERT INTO raw.telegram_messages
    (message_id, channel_name, message_date, message_text,
     has_media, is_photo, image_path, views, forwards, scraped_at)
VALUES %s
ON CONFLICT (message_id, channel_name) DO UPDATE SET
    message_text = EXCLUDED.message_text,
    views        = EXCLUDED.views,
    forwards     = EXCLUDED.forwards,
    loaded_at    = NOW();
"""


def _get_connection():
    return psycopg2.connect(settings.database_url)


def _collect_records() -> list[tuple]:
    """Walk the data lake and collect all message records."""
    rows = []
    messages_root = settings.messages_dir
    for json_file in sorted(messages_root.rglob("*.json")):
        with open(json_file, encoding="utf-8") as fh:
            records = json.load(fh)
        for r in records:
            rows.append((
                r.get("message_id"),
                r.get("channel_name"),
                r.get("message_date"),
                r.get("message_text", ""),
                r.get("has_media", False),
                r.get("is_photo", False),
                r.get("image_path"),
                r.get("views", 0),
                r.get("forwards", 0),
                r.get("scraped_at"),
            ))
    return rows


def load_raw_to_postgres() -> int:
    """Main loader — returns number of rows upserted."""
    log.info("Starting raw data load to PostgreSQL")
    rows = _collect_records()
    if not rows:
        log.warning("No JSON records found in data lake. Run the scraper first.")
        return 0
    log.info(f"Collected {len(rows)} records from data lake")
    conn = _get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SCHEMA_SQL)
                cur.execute(CREATE_TABLE_SQL)
                execute_values(cur, INSERT_SQL, rows, page_size=500)
                log.info(f"Upserted {len(rows)} rows into raw.telegram_messages")
    finally:
        conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_raw_to_postgres()
    print(f"Loaded {n} records.")

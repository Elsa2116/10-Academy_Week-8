"""
src/config.py — Single source of truth for all project settings.

Credentials are loaded exclusively from environment variables (via .env file).
Never import raw os.environ values elsewhere in the codebase — always use
`from src.config import settings` so the validation layer is always applied.

Usage:
    from src.config import settings
    conn = psycopg2.connect(settings.database_url)
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram API credentials ───────────────────────────────────────────
    # Source: https://my.telegram.org → API Development Tools
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_session_name: str = "telegram_session"

    # ── PostgreSQL connection ──────────────────────────────────────────────
    # These same variables are read by dbt (via profiles.yml env_var())
    # and by FastAPI (via api/database.py).
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medical_warehouse"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    @property
    def database_url(self) -> str:
        """Construct DSN from individual env vars (never stored as one secret)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── YOLO ──────────────────────────────────────────────────────────────
    yolo_model: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.25

    # ── Data lake directory layout ─────────────────────────────────────────
    # Structure:
    #   data/raw/telegram_messages/YYYY-MM-DD/{channel}.json
    #   data/raw/images/{channel}/{message_id}.jpg
    #   data/processed/yolo_detections.csv
    #   logs/{component}.log
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    images_dir: Path = Path("data/raw/images")
    messages_dir: Path = Path("data/raw/telegram_messages")
    logs_dir: Path = Path("logs")

    # ── Telegram channels to scrape ────────────────────────────────────────
    telegram_channels: list[str] = [
        "lobelia4cosmetics",
        "tikvahethiopia",
        "CheMed123",
        "DoctorsETBot",
        "eahci",
    ]


settings = Settings()

# Ensure all required directories exist on import.
# This runs once when any module does `from src.config import settings`.
for _dir in [
    settings.data_dir,
    settings.raw_dir,
    settings.processed_dir,
    settings.images_dir,
    settings.messages_dir,
    settings.logs_dir,
]:
    _dir.mkdir(parents=True, exist_ok=True)

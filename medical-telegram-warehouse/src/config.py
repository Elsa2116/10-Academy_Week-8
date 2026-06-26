from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_session_name: str = "telegram_session"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medical_warehouse"
    postgres_user: str = "warehouse_user"
    postgres_password: str = "warehouse_pass"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # YOLO
    yolo_model: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.25

    # Paths
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    images_dir: Path = Path("data/raw/images")
    messages_dir: Path = Path("data/raw/telegram_messages")
    logs_dir: Path = Path("logs")

    # Channels to scrape
    telegram_channels: list[str] = [
        "lobelia4cosmetics",
        "tikvahethiopia",
        "CheMed123",
        "DoctorsETBot",
        "eahci",
    ]


settings = Settings()

# Ensure directories exist
for d in [
    settings.data_dir,
    settings.raw_dir,
    settings.processed_dir,
    settings.images_dir,
    settings.messages_dir,
    settings.logs_dir,
]:
    d.mkdir(parents=True, exist_ok=True)

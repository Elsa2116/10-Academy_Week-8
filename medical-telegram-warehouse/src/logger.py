import sys
from pathlib import Path
from loguru import logger

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logger(name: str = "pipeline") -> "logger":
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.add(
        LOG_DIR / f"{name}.log",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function}:{line} - {message}",
        level="DEBUG",
    )
    return logger


pipeline_logger = setup_logger("pipeline")
scraper_logger = setup_logger("scraper")
yolo_logger = setup_logger("yolo")
loader_logger = setup_logger("loader")

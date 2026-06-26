"""
Task 5 — Dagster Pipeline Orchestration
Defines the full ELT pipeline as Dagster ops and a scheduled job.
"""

import subprocess
from pathlib import Path

from dagster import (
    AssetMaterialization,
    Definitions,
    Output,
    RunRequest,
    ScheduleDefinition,
    job,
    op,
    schedule,
)

from src.config import settings
from src.loader import load_raw_to_postgres
from src.yolo_detect import load_detections_to_postgres, run_detection


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------

@op(description="Scrapes Telegram channels and writes JSON to the data lake.")
def scrape_telegram_data(context):
    """Runs the Telethon-based scraper for all configured channels."""
    import asyncio

    from src.scraper import TelegramScraper

    scraper = TelegramScraper(limit_per_channel=200)
    summary = asyncio.run(scraper.run())
    total = sum(summary.values())
    context.log.info(f"Scraped {total} messages across {len(summary)} channels")
    yield AssetMaterialization(
        asset_key="telegram_raw_messages",
        description=f"Scraped {total} messages",
        metadata={"channels": str(list(summary.keys())), "total_messages": total},
    )
    yield Output(summary)


@op(description="Loads raw JSON files from the data lake into PostgreSQL raw schema.")
def load_raw_to_postgres_op(context, scrape_result):
    """Reads all JSON files and upserts them into raw.telegram_messages."""
    n = load_raw_to_postgres()
    context.log.info(f"Loaded {n} raw records into PostgreSQL")
    yield AssetMaterialization(
        asset_key="raw_telegram_messages_table",
        description=f"Loaded {n} rows",
        metadata={"row_count": n},
    )
    yield Output(n)


@op(description="Runs dbt to build staging and mart models.")
def run_dbt_transformations(context, load_result):
    """Executes dbt deps + dbt run + dbt test."""
    dbt_dir = Path("medical_warehouse")
    for cmd in [
        ["dbt", "deps", "--project-dir", str(dbt_dir)],
        ["dbt", "run", "--project-dir", str(dbt_dir)],
        ["dbt", "test", "--project-dir", str(dbt_dir)],
    ]:
        context.log.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        context.log.info(result.stdout)
        if result.returncode != 0:
            context.log.error(result.stderr)
            raise Exception(f"dbt command failed: {' '.join(cmd)}")
    context.log.info("dbt transformations complete")
    yield AssetMaterialization(
        asset_key="dbt_mart_models",
        description="All dbt models built and tested",
    )
    yield Output("success")


@op(description="Runs YOLOv8 object detection on downloaded images.")
def run_yolo_enrichment(context, dbt_result):
    """Detects objects in all downloaded images and loads results to the warehouse."""
    csv_path = run_detection()
    n = load_detections_to_postgres(csv_path)
    context.log.info(f"YOLO enrichment complete: {n} rows loaded")
    yield AssetMaterialization(
        asset_key="yolo_detections_table",
        description=f"Loaded {n} YOLO detection rows",
        metadata={"row_count": n, "csv_path": str(csv_path)},
    )
    yield Output(n)


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

@job(
    name="medical_telegram_pipeline",
    description="End-to-end ELT pipeline: Scrape → Load → Transform → Enrich",
)
def medical_pipeline():
    scrape_result = scrape_telegram_data()
    load_result = load_raw_to_postgres_op(scrape_result)
    dbt_result = run_dbt_transformations(load_result)
    run_yolo_enrichment(dbt_result)


# ---------------------------------------------------------------------------
# Schedule (daily at 02:00 UTC)
# ---------------------------------------------------------------------------

daily_schedule = ScheduleDefinition(
    job=medical_pipeline,
    cron_schedule="0 2 * * *",
    name="daily_medical_pipeline",
    description="Runs the full ELT pipeline every day at 02:00 UTC",
)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

defs = Definitions(
    jobs=[medical_pipeline],
    schedules=[daily_schedule],
)

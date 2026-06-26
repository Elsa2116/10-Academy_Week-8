"""
run_pipeline.py — Run all 5 pipeline tasks in order with one command.

Usage:
    python scripts/run_pipeline.py               # full pipeline (real Telegram)
    python scripts/run_pipeline.py --sample      # use sample data (no Telegram API needed)
    python scripts/run_pipeline.py --skip-scrape # skip scraping, load existing JSON
    python scripts/run_pipeline.py --skip-yolo   # skip YOLO (no images downloaded)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


# ── Colours for terminal output ────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def banner(step: int, total: int, title: str):
    print(f"\n{BOLD}{CYAN}{'─'*55}{RESET}")
    print(f"{BOLD}{CYAN}  Step {step}/{total} — {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*55}{RESET}\n")


def ok(msg: str):
    print(f"{GREEN}✔  {msg}{RESET}")


def warn(msg: str):
    print(f"{YELLOW}⚠  {msg}{RESET}")


def fail(msg: str):
    print(f"{RED}✘  {msg}{RESET}")


def run(cmd: list[str], label: str) -> bool:
    """Run a command, stream output, return True on success."""
    print(f"  $ {' '.join(cmd)}\n")
    result = subprocess.run(cmd, text=True)
    if result.returncode == 0:
        ok(f"{label} — done")
        return True
    else:
        fail(f"{label} — FAILED (exit {result.returncode})")
        return False


def check_docker():
    """Warn if Docker is not running."""
    r = subprocess.run(
        ["docker", "info"], capture_output=True, text=True
    )
    if r.returncode != 0:
        warn("Docker is not running — make sure PostgreSQL is up (docker-compose up -d postgres)")


def main():
    parser = argparse.ArgumentParser(description="Run the Medical Telegram Pipeline")
    parser.add_argument("--sample",      action="store_true", help="Generate sample data instead of scraping Telegram")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip Task 1 — use existing JSON in data lake")
    parser.add_argument("--skip-yolo",   action="store_true", help="Skip Task 3 — skip YOLO object detection")
    args = parser.parse_args()

    start = time.time()

    print(f"\n{BOLD}{'═'*55}")
    print("  ETHIOPIAN MEDICAL TELEGRAM PIPELINE")
    print(f"{'═'*55}{RESET}")
    print("  Kara Solutions — Data Engineering Week 8")
    print(f"  Mode: {'SAMPLE DATA' if args.sample else 'LIVE TELEGRAM'}\n")

    check_docker()
    steps_ok = []

    # ── Task 1: Scrape ──────────────────────────────────────────────────────
    banner(1, 5, "Data Scraping & Collection")
    if args.sample:
        ok("Using sample data generator (--sample flag set)")
        steps_ok.append(run(
            [sys.executable, "scripts/generate_sample_data.py"],
            "Sample data generation"
        ))
    elif args.skip_scrape:
        warn("Skipping scrape — using existing JSON in data/raw/telegram_messages/")
        steps_ok.append(True)
    else:
        steps_ok.append(run(
            [sys.executable, "-m", "src.scraper"],
            "Telegram scraping"
        ))

    # ── Task 1b: Load raw → PostgreSQL ──────────────────────────────────────
    banner(1, 5, "Load Raw Data → PostgreSQL")
    steps_ok.append(run(
        [sys.executable, "-m", "src.loader"],
        "Raw data load to PostgreSQL"
    ))

    # ── Task 2: dbt ─────────────────────────────────────────────────────────
    banner(2, 5, "dbt Transformations (Star Schema)")
    dbt_dir = Path("medical_warehouse")

    print("  Installing dbt packages...")
    steps_ok.append(run(
        ["dbt", "deps", "--project-dir", str(dbt_dir)],
        "dbt deps"
    ))

    print("\n  Building staging + mart models...")
    steps_ok.append(run(
        ["dbt", "run", "--project-dir", str(dbt_dir)],
        "dbt run"
    ))

    print("\n  Running data quality tests...")
    steps_ok.append(run(
        ["dbt", "test", "--project-dir", str(dbt_dir)],
        "dbt test"
    ))

    # ── Task 3: YOLO ────────────────────────────────────────────────────────
    banner(3, 5, "YOLO Object Detection")
    if args.skip_yolo:
        warn("Skipping YOLO (--skip-yolo flag set). Generating sample detections instead...")
        steps_ok.append(run(
            [sys.executable, "scripts/generate_sample_yolo.py"],
            "Sample YOLO data"
        ))
        steps_ok.append(run(
            [sys.executable, "-c",
             "from src.yolo_detect import load_detections_to_postgres; load_detections_to_postgres()"],
            "Load YOLO results to PostgreSQL"
        ))
    elif args.sample:
        # Sample mode → also sample YOLO
        steps_ok.append(run(
            [sys.executable, "scripts/generate_sample_yolo.py"],
            "Sample YOLO data"
        ))
        steps_ok.append(run(
            [sys.executable, "-c",
             "from src.yolo_detect import load_detections_to_postgres; load_detections_to_postgres()"],
            "Load YOLO results to PostgreSQL"
        ))
    else:
        steps_ok.append(run(
            [sys.executable, "-m", "src.yolo_detect"],
            "YOLO detection + load"
        ))

    # ── Task 4: FastAPI ─────────────────────────────────────────────────────
    banner(4, 5, "Analytical API (FastAPI)")
    print("  The API server needs to stay running — open a NEW terminal and run:")
    print(f"\n  {BOLD}uvicorn api.main:app --reload --port 8000{RESET}")
    print("\n  Then open:  http://localhost:8000/docs")
    warn("API not auto-started (it's a long-running server). Start it manually in a new terminal.")
    steps_ok.append(True)

    # ── Task 5: Dagster ─────────────────────────────────────────────────────
    banner(5, 5, "Dagster Orchestration")
    print("  Dagster UI also needs its own terminal. Run:")
    print(f"\n  {BOLD}dagster dev -f pipeline.py{RESET}")
    print("\n  Then open:  http://localhost:3000")
    warn("Dagster not auto-started. Start it manually in a new terminal.")
    steps_ok.append(True)

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.time() - start
    passed  = sum(steps_ok)
    total   = len(steps_ok)

    print(f"\n{BOLD}{'═'*55}")
    print("  PIPELINE SUMMARY")
    print(f"{'═'*55}{RESET}")
    print(f"  Elapsed  : {elapsed:.0f}s")
    print(f"  Steps    : {passed}/{total} passed")

    if passed == total:
        print(f"\n{GREEN}{BOLD}  ✔ Pipeline complete!{RESET}")
        print(f"\n  Next steps:")
        print(f"  1. Start API   → uvicorn api.main:app --reload")
        print(f"  2. Start UI    → dagster dev -f pipeline.py")
        print(f"  3. Run EDA     → jupyter notebook notebooks/eda.ipynb")
        print(f"  4. dbt docs    → cd medical_warehouse && dbt docs generate && dbt docs serve")
    else:
        failed = total - passed
        print(f"\n{RED}{BOLD}  ✘ {failed} step(s) failed. Check the output above.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()

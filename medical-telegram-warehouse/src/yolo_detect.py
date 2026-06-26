"""
Task 3 — YOLO Object Detection
Runs YOLOv8 on downloaded Telegram images and saves detection results
to a CSV for loading into the data warehouse.
"""

import csv
from pathlib import Path

from ultralytics import YOLO

from src.config import settings
from src.logger import yolo_logger as log

RESULTS_CSV = settings.processed_dir / "yolo_detections.csv"

# Categories derived from detected COCO object classes
PRODUCT_CLASSES = {"bottle", "cup", "bowl", "vase", "book", "box", "package"}
PERSON_CLASSES = {"person"}


def classify_image(detected_labels: list[str]) -> str:
    """
    Map YOLO class labels to a business category.

    Rules:
        promotional      → person + product object detected
        product_display  → product object detected, no person
        lifestyle        → person detected, no product
        other            → nothing relevant detected
    """
    has_person = any(lbl in PERSON_CLASSES for lbl in detected_labels)
    has_product = any(lbl in PRODUCT_CLASSES for lbl in detected_labels)

    if has_person and has_product:
        return "promotional"
    if has_product:
        return "product_display"
    if has_person:
        return "lifestyle"
    return "other"


def _parse_message_id_and_channel(image_path: Path) -> tuple[int | None, str | None]:
    """
    Images are stored at:
        data/raw/images/{channel_name}/{message_id}.jpg
    """
    try:
        message_id = int(image_path.stem)
        channel_name = image_path.parent.name
        return message_id, channel_name
    except (ValueError, IndexError):
        return None, None


def run_detection(model_path: str = settings.yolo_model) -> Path:
    """
    Scan all images in the data lake, run YOLOv8, and write CSV results.
    Returns the path to the output CSV.
    """
    log.info(f"Loading YOLO model: {model_path}")
    model = YOLO(model_path)

    images = list(settings.images_dir.rglob("*.jpg")) + list(
        settings.images_dir.rglob("*.png")
    )
    log.info(f"Found {len(images)} images to process")

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "message_id",
                "channel_name",
                "image_path",
                "detected_objects",
                "detected_classes",
                "max_confidence",
                "image_category",
                "num_detections",
            ],
        )
        writer.writeheader()

        for img_path in images:
            message_id, channel_name = _parse_message_id_and_channel(img_path)
            if message_id is None:
                log.warning(f"Skipping unrecognised image path: {img_path}")
                continue

            try:
                results = model(
                    str(img_path),
                    conf=settings.yolo_confidence_threshold,
                    verbose=False,
                )
                result = results[0]
                boxes = result.boxes

                if boxes is None or len(boxes) == 0:
                    detected_labels: list[str] = []
                    max_conf = 0.0
                else:
                    detected_labels = [
                        model.names[int(cls)] for cls in boxes.cls.tolist()
                    ]
                    max_conf = float(boxes.conf.max().item())

                category = classify_image(detected_labels)
                writer.writerow(
                    {
                        "message_id": message_id,
                        "channel_name": channel_name,
                        "image_path": str(img_path),
                        "detected_objects": "; ".join(detected_labels),
                        "detected_classes": ", ".join(sorted(set(detected_labels))),
                        "max_confidence": round(max_conf, 4),
                        "image_category": category,
                        "num_detections": len(detected_labels),
                    }
                )
                log.debug(f"{img_path.name} → {category} ({detected_labels})")

            except Exception as exc:
                log.error(f"Detection failed for {img_path}: {exc}")

    log.info(f"Detection complete. Results saved to {RESULTS_CSV}")
    return RESULTS_CSV


def load_detections_to_postgres(csv_path: Path = RESULTS_CSV) -> int:
    """Load YOLO CSV results into raw.yolo_detections table in PostgreSQL."""
    import csv as csv_mod

    import psycopg2
    from psycopg2.extras import execute_values

    CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS raw.yolo_detections (
        id               SERIAL PRIMARY KEY,
        message_id       BIGINT,
        channel_name     TEXT,
        image_path       TEXT,
        detected_objects TEXT,
        detected_classes TEXT,
        max_confidence   NUMERIC(6,4),
        image_category   TEXT,
        num_detections   INTEGER,
        loaded_at        TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (message_id, channel_name)
    );
    """
    INSERT_SQL = """
    INSERT INTO raw.yolo_detections
        (message_id, channel_name, image_path, detected_objects,
         detected_classes, max_confidence, image_category, num_detections)
    VALUES %s
    ON CONFLICT (message_id, channel_name) DO UPDATE SET
        image_category   = EXCLUDED.image_category,
        max_confidence   = EXCLUDED.max_confidence,
        loaded_at        = NOW();
    """
    rows: list[tuple] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv_mod.DictReader(fh)
        for row in reader:
            rows.append((
                int(row["message_id"]),
                row["channel_name"],
                row["image_path"],
                row["detected_objects"],
                row["detected_classes"],
                float(row["max_confidence"]) if row["max_confidence"] else 0.0,
                row["image_category"],
                int(row["num_detections"]) if row["num_detections"] else 0,
            ))

    if not rows:
        log.warning("No YOLO detection rows to load.")
        return 0

    conn = psycopg2.connect(settings.database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
                cur.execute(CREATE_SQL)
                execute_values(cur, INSERT_SQL, rows, page_size=500)
    finally:
        conn.close()
    log.info(f"Loaded {len(rows)} YOLO detection rows into raw.yolo_detections")
    return len(rows)


if __name__ == "__main__":
    csv_out = run_detection()
    load_detections_to_postgres(csv_out)

"""
Generate realistic sample YOLO detection results CSV for testing.
Run this INSTEAD of yolo_detect.py when you don't have real images yet.
Usage: python scripts/generate_sample_yolo.py
"""

import csv
import json
import random
from pathlib import Path

CATEGORIES = ["promotional", "product_display", "lifestyle", "other"]
WEIGHTS     = [0.30, 0.45, 0.15, 0.10]

OBJECT_SETS = {
    "promotional":     ["person", "bottle"],
    "product_display": ["bottle", "bowl"],
    "lifestyle":       ["person"],
    "other":           ["chair", "potted plant"],
}


def main():
    messages_root = Path("data/raw/telegram_messages")
    out_path = Path("data/processed")
    out_path.mkdir(parents=True, exist_ok=True)
    csv_path = out_path / "yolo_detections.csv"

    rows = []
    for json_file in sorted(messages_root.rglob("*.json")):
        with open(json_file, encoding="utf-8") as fh:
            records = json.load(fh)
        for r in records:
            if not r.get("is_photo"):
                continue
            category = random.choices(CATEGORIES, WEIGHTS)[0]
            objects  = OBJECT_SETS[category]
            rows.append({
                "message_id":      r["message_id"],
                "channel_name":    r["channel_name"],
                "image_path":      r.get("image_path", ""),
                "detected_objects": "; ".join(objects),
                "detected_classes": ", ".join(sorted(set(objects))),
                "max_confidence":  round(random.uniform(0.45, 0.95), 4),
                "image_category":  category,
                "num_detections":  len(objects),
            })

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} YOLO sample rows → {csv_path}")
    print("Now run:  python -m src.yolo_detect  (the load step) to push to PostgreSQL")


if __name__ == "__main__":
    main()

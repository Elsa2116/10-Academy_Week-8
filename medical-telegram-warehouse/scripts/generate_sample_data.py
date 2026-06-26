"""
Generate realistic sample data for local testing.
Run this INSTEAD of the real scraper when you don't have Telegram API credentials yet.
Usage: python scripts/generate_sample_data.py
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHANNELS = [
    "CheMed123",
    "lobelia4cosmetics",
    "tikvahethiopia",
    "DoctorsETBot",
    "eahci",
]

CHANNEL_TYPE = {
    "CheMed123": "Medical",
    "lobelia4cosmetics": "Cosmetics",
    "tikvahethiopia": "Pharmaceutical",
    "DoctorsETBot": "Medical",
    "eahci": "Medical",
}

SAMPLE_TEXTS = [
    "Paracetamol 500mg available — 50 tablets for 45 ETB. Contact us now!",
    "Amoxicillin 250mg/5ml oral suspension — 100ml bottle 120 ETB",
    "Vitamin C 1000mg effervescent tablets now in stock. 20 tabs 80 ETB",
    "Ibuprofen 400mg — relief from pain and fever. 24 tablets 60 ETB",
    "Metformin 500mg for diabetes management. 100 tabs 150 ETB",
    "Omeprazole 20mg capsules — 14 caps for 70 ETB",
    "Cetaphil moisturizing lotion 250ml — 450 ETB",
    "Sunscreen SPF 50+ cream — 60ml, 320 ETB",
    "Hair growth serum — biotin enriched formula 280 ETB",
    "Antiseptic wound wash 200ml — 95 ETB",
    "Chloroquine tablets available for malaria prevention",
    "Albendazole 400mg — deworming tablets, 1 tab 25 ETB",
    "New arrival: Multivitamin gummies for children 90 ETB",
    "Cough syrup — honey and lemon, 100ml bottle 85 ETB",
    "Antifungal cream 30g — 110 ETB. Very effective!",
    "Blood pressure monitor digital — 1200 ETB",
    "Disposable surgical masks — box of 50, 180 ETB",
    "Hand sanitizer 500ml — 75% alcohol, 95 ETB",
    "Thermometer digital infrared — 850 ETB",
    "Pregnancy test kit — accurate results in 3 minutes, 45 ETB",
    "Insulin syringes 1ml — box of 100, 220 ETB",
    "Doxycycline 100mg capsules for infection treatment",
    "Zinc tablets 50mg — immune support, 60 tabs 130 ETB",
    "Aloe vera gel for skin soothing — 250ml, 190 ETB",
    "Strepsils throat lozenges — 24 pack 95 ETB",
]

BASE_DATE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def random_date(start: datetime, days: int = 180) -> datetime:
    return start + timedelta(
        days=random.randint(0, days),
        hours=random.randint(6, 22),
        minutes=random.randint(0, 59),
    )


def generate_messages(channel: str, n: int = 80) -> list[dict]:
    records = []
    for i in range(1, n + 1):
        msg_date = random_date(BASE_DATE)
        has_photo = random.random() < 0.35
        records.append({
            "message_id": 10000 + i + CHANNELS.index(channel) * 1000,
            "channel_name": channel,
            "message_date": msg_date.isoformat(),
            "message_text": random.choice(SAMPLE_TEXTS),
            "has_media": has_photo,
            "is_photo": has_photo,
            "image_path": (
                f"data/raw/images/{channel}/{10000 + i}.jpg" if has_photo else None
            ),
            "views": random.randint(50, 8000),
            "forwards": random.randint(0, 300),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
    return records


def main():
    base = Path("data/raw/telegram_messages")
    base.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = base / today
    out_dir.mkdir(exist_ok=True)

    total = 0
    for channel in CHANNELS:
        records = generate_messages(channel, n=80)
        out_file = out_dir / f"{channel}.json"
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)
        total += len(records)
        print(f"  Generated {len(records)} records → {out_file}")

    print(f"\nDone. {total} sample messages written to data/raw/telegram_messages/{today}/")
    print("Now run:  python -m src.loader  to load them into PostgreSQL")


if __name__ == "__main__":
    main()

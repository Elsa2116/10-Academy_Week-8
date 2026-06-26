## Medical Telegram Warehouse

> **End-to-end data pipeline for Ethiopian medical & pharmaceutical Telegram channels**
> Telegram scraping → PostgreSQL data lake → dbt star schema → YOLOv8 enrichment → FastAPI analytics → Dagster orchestration

---

## Architecture

```
Telegram Channels
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Task 1 — Extract & Load  (src/scraper.py + src/loader.py)      │
│  Telethon → JSON data lake → raw.telegram_messages (PostgreSQL) │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Task 2 — Transform  (medical_warehouse/ — dbt)                  │
│  raw → staging.stg_telegram_messages                             │
│      → marts.dim_channels                                        │
│      → marts.dim_dates                                           │
│      → marts.fct_messages   ◄── star schema fact table          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Task 3 — Enrich  (src/yolo_detect.py)                           │
│  YOLOv8 nano → raw.yolo_detections → marts.fct_image_detections │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Task 4 — Analytical API  (api/main.py — FastAPI)                │
│  GET /api/reports/top-products                                   │
│  GET /api/channels/{name}/activity                               │
│  GET /api/search/messages                                        │
│  GET /api/reports/visual-content                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Task 5 — Orchestration  (pipeline.py — Dagster)                 │
│  Scheduled daily at 02:00 UTC via dagster dev                    │
└─────────────────────────────────────────────────────────────────┘
```

## Star Schema

```
              ┌──────────────┐
              │  dim_dates   │
              │  date_key PK │
              └──────┬───────┘
                     │ FK
┌──────────────┐     │     ┌───────────────────────────────────┐
│ dim_channels │     │     │         fct_messages               │
│ channel_key  ├─────┼─────┤  message_id                        │
│ channel_name │  FK │     │  channel_key  FK → dim_channels    │
│ channel_type │     │     │  date_key     FK → dim_dates       │
│ total_posts  │     └─────┤  message_text                      │
│ avg_views    │           │  message_length                    │
└──────────────┘           │  view_count                        │
                           │  forward_count                     │
                           │  has_image                         │
                           └──────────────────┬─────────────────┘
                                              │ message_id JOIN
                           ┌──────────────────▼─────────────────┐
                           │       fct_image_detections          │
                           │  message_id                         │
                           │  channel_key  FK → dim_channels     │
                           │  date_key     FK → dim_dates        │
                           │  image_category                     │
                           │  confidence_score                   │
                           │  num_detections                     │
                           └─────────────────────────────────────┘
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/<your-org>/medical-telegram-warehouse.git
cd medical-telegram-warehouse

cp .env.example .env
# Edit .env with your Telegram API credentials and DB password
```

### 2. Start infrastructure with Docker Compose

```bash
docker-compose up -d postgres
```

### 3. Create a Python virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Task 1 — Scrape Telegram channels

```bash
python -m src.scraper
```

Outputs:

- `data/raw/telegram_messages/YYYY-MM-DD/{channel}.json`
- `data/raw/images/{channel}/{message_id}.jpg`
- `logs/scraper.log`

### 5. Load raw data to PostgreSQL

```bash
python -m src.loader
```

### 6. Task 2 — Run dbt transformations

```bash
cd medical_warehouse
dbt deps          # install dbt_utils package
dbt run           # build staging + mart models
dbt test          # run all schema + custom tests
dbt docs generate && dbt docs serve   # open docs at http://localhost:8080
cd ..
```

### 7. Task 3 — YOLO enrichment

```bash
python -m src.yolo_detect
```

Outputs: `data/processed/yolo_detections.csv` → loaded into `raw.yolo_detections`

### 8. Task 4 — Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

Browse to:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 9. Task 5 — Launch Dagster orchestration

```bash
dagster dev -f pipeline.py
```

Open **Dagster UI** at http://localhost:3000, select `medical_telegram_pipeline`, and click **Materialize All**.

---

## Project Structure

```
medical-telegram-warehouse/
├── .github/workflows/unittests.yml   # CI — pytest on push
├── .env.example                      # Template — copy to .env
├── docker-compose.yml                # PostgreSQL + API + Dagster
├── Dockerfile
├── requirements.txt
├── pipeline.py                       # Dagster job definition
│
├── src/
│   ├── config.py                     # Settings (pydantic-settings + .env)
│   ├── logger.py                     # Loguru logger factory
│   ├── scraper.py                    # Task 1 — Telegram scraper
│   ├── loader.py                     # Task 2 — JSON → PostgreSQL loader
│   └── yolo_detect.py               # Task 3 — YOLO detection + loader
│
├── api/
│   ├── main.py                       # Task 4 — FastAPI application
│   ├── database.py                   # SQLAlchemy engine + session
│   └── schemas.py                    # Pydantic request/response models
│
├── medical_warehouse/                # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml                  # DB connection (reads from env vars)
│   ├── packages.yml                  # dbt_utils dependency
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_telegram_messages.sql
│   │   │   └── schema.yml
│   │   └── marts/
│   │       ├── dim_channels.sql
│   │       ├── dim_dates.sql
│   │       ├── fct_messages.sql
│   │       ├── fct_image_detections.sql
│   │       └── schema.yml
│   └── tests/
│       ├── assert_no_future_messages.sql
│       ├── assert_positive_views.sql
│       └── assert_fk_messages_to_channels.sql
│
├── data/
│   ├── raw/
│   │   ├── telegram_messages/        # Partitioned JSON (YYYY-MM-DD/channel.json)
│   │   └── images/                   # channel_name/message_id.jpg
│   └── processed/
│       └── yolo_detections.csv
│
├── tests/                            # pytest unit tests
│   ├── test_loader.py
│   ├── test_yolo_classify.py
│   └── test_api.py
│
├── scripts/
│   └── init_db.sql                   # DB schema init (runs on container start)
│
└── logs/                             # Loguru log files
```

---

## API Endpoints

| Method | Path                                              | Description                                   |
| ------ | ------------------------------------------------- | --------------------------------------------- |
| `GET`  | `/health`                                         | Database connectivity check                   |
| `GET`  | `/api/reports/top-products?limit=10`              | Top mentioned product terms                   |
| `GET`  | `/api/channels/{channel_name}/activity`           | Daily posting metrics for a channel           |
| `GET`  | `/api/search/messages?query=paracetamol&limit=20` | Keyword search across all messages            |
| `GET`  | `/api/reports/visual-content`                     | Image usage & YOLO category stats per channel |
| `GET`  | `/api/channels`                                   | List all channels with summary stats          |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## dbt Tests

| Test                                  | Type   | What it checks           |
| ------------------------------------- | ------ | ------------------------ |
| `unique` / `not_null` on primary keys | Schema | Data integrity           |
| `accepted_values` on `channel_type`   | Schema | Enum safety              |
| `relationships` on FK columns         | Schema | Referential integrity    |
| `assert_no_future_messages`           | Custom | No clock-skew in scraper |
| `assert_positive_views`               | Custom | No negative view counts  |
| `assert_fk_messages_to_channels`      | Custom | No orphaned fact rows    |

---

## Environment Variables

| Variable                    | Description                                |
| --------------------------- | ------------------------------------------ |
| `TELEGRAM_API_ID`           | From https://my.telegram.org               |
| `TELEGRAM_API_HASH`         | From https://my.telegram.org               |
| `TELEGRAM_PHONE`            | Your registered phone number               |
| `POSTGRES_HOST`             | PostgreSQL host (default: `localhost`)     |
| `POSTGRES_PORT`             | PostgreSQL port (default: `5432`)          |
| `POSTGRES_DB`               | Database name                              |
| `POSTGRES_USER`             | Database user                              |
| `POSTGRES_PASSWORD`         | Database password                          |
| `YOLO_MODEL`                | YOLO weights file (default: `yolov8n.pt`)  |
| `YOLO_CONFIDENCE_THRESHOLD` | Min detection confidence (default: `0.25`) |

---

## Channels Scraped

| Channel           | Type               |
| ----------------- | ------------------ |
| CheMed123         | Medical products   |
| lobelia4cosmetics | Cosmetics & health |
| tikvahethiopia    | Pharmaceuticals    |
| DoctorsETBot      | Medical            |
| eahci             | Health             |

Add more channels to `TELEGRAM_CHANNELS` in `src/config.py`.

---

## Design Decisions

1. **ELT not ETL** — Raw data lands in PostgreSQL first (`raw` schema), transformations happen inside the warehouse via dbt. This preserves the original data and makes reprocessing cheap.
2. **Star schema** — Two dimension tables (`dim_channels`, `dim_dates`) and two fact tables (`fct_messages`, `fct_image_detections`) keep queries simple and performant for analytical workloads.
3. **Surrogate keys via dbt_utils** — `generate_surrogate_key` produces stable MD5-based keys so dimension tables can be truncated and rebuilt without breaking foreign key relationships.
4. **YOLOv8 nano** — The smallest model that runs on CPU; sufficient for categorising promotional vs. product images without requiring a GPU.
5. **Dagster over Airflow** — Better local development experience, first-class asset lineage, and no separate scheduler process to manage.

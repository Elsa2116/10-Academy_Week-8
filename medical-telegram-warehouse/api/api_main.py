"""
Task 4 — Analytical API (FastAPI)
Exposes cleaned dbt mart data through REST endpoints.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.database import check_connection, get_db
from api.schemas import (
    ChannelActivityResponse,
    ChannelsListResponse,
    ChannelSummary,
    ChannelVisualStats,
    DailyActivity,
    HealthResponse,
    MessageItem,
    MessageSearchResponse,
    TopProductItem,
    TopProductsResponse,
    VisualContentResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Medical Warehouse API starting up...")
    yield
    print("Medical Warehouse API shutting down...")


app = FastAPI(
    title="Ethiopian Medical Telegram Warehouse API",
    description=(
        "Analytical API exposing insights from Ethiopian medical & pharmaceutical "
        "Telegram channels. Data is processed through a dbt star-schema pipeline."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Check API and database connectivity."""
    db_ok = check_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unreachable",
    )


# ---------------------------------------------------------------------------
# Endpoint 1 — Top Products
# ---------------------------------------------------------------------------

TOP_PRODUCTS_SQL = """
WITH word_counts AS (
    SELECT
        LOWER(word) AS term,
        channel_name
    FROM
        marts.fct_messages,
        LATERAL unnest(
            string_to_array(
                regexp_replace(
                    LOWER(message_text),
                    '[^a-z0-9 ]', ' ', 'g'
                ),
                ' '
            )
        ) AS word
    WHERE
        LENGTH(word) > 3
        AND word NOT IN (
            'that','this','with','from','have','will','what',
            'your','been','they','were','also','into','more',
            'than','some','when','then','over','each','just'
        )
)
SELECT
    term,
    COUNT(*)          AS mention_count,
    COUNT(DISTINCT channel_name) AS channels
FROM word_counts
WHERE term <> ''
GROUP BY term
ORDER BY mention_count DESC
LIMIT :limit;
"""


@app.get(
    "/api/reports/top-products",
    response_model=TopProductsResponse,
    tags=["Reports"],
    summary="Top mentioned product terms across all channels",
)
def top_products(
    limit: int = Query(10, ge=1, le=100, description="Number of terms to return"),
    db: Session = Depends(get_db),
):
    """
    Returns the most frequently mentioned product terms across all Telegram channels,
    derived from tokenizing message text in the fact table.
    """
    rows = db.execute(text(TOP_PRODUCTS_SQL), {"limit": limit}).fetchall()
    items = [
        TopProductItem(term=r.term, mention_count=r.mention_count, channels=r.channels)
        for r in rows
    ]
    return TopProductsResponse(items=items, limit=limit, total=len(items))


# ---------------------------------------------------------------------------
# Endpoint 2 — Channel Activity
# ---------------------------------------------------------------------------

CHANNEL_SUMMARY_SQL = """
SELECT
    dc.channel_name,
    COUNT(fm.message_id)          AS total_messages,
    COALESCE(SUM(fm.view_count),0)  AS total_views
FROM marts.fct_messages fm
JOIN marts.dim_channels dc ON fm.channel_key = dc.channel_key
WHERE dc.channel_name = :channel
GROUP BY dc.channel_name;
"""

CHANNEL_DAILY_SQL = """
SELECT
    dd.full_date                      AS activity_date,
    COUNT(fm.message_id)              AS message_count,
    COALESCE(SUM(fm.view_count),0)    AS total_views,
    COALESCE(SUM(fm.forward_count),0) AS total_forwards,
    COALESCE(SUM(fm.has_image::int),0) AS images
FROM marts.fct_messages fm
JOIN marts.dim_channels dc ON fm.channel_key = dc.channel_key
JOIN marts.dim_dates     dd ON fm.date_key    = dd.date_key
WHERE dc.channel_name = :channel
GROUP BY dd.full_date
ORDER BY dd.full_date DESC
LIMIT 30;
"""


@app.get(
    "/api/channels/{channel_name}/activity",
    response_model=ChannelActivityResponse,
    tags=["Channels"],
    summary="Posting activity and trends for a specific channel",
)
def channel_activity(channel_name: str, db: Session = Depends(get_db)):
    """
    Returns up to 30 days of daily posting metrics for the given channel,
    including message count, views, forwards, and image count.
    """
    summary = db.execute(text(CHANNEL_SUMMARY_SQL), {"channel": channel_name}).fetchone()
    if not summary or summary.total_messages == 0:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_name}' not found.")

    daily_rows = db.execute(text(CHANNEL_DAILY_SQL), {"channel": channel_name}).fetchall()
    avg_views = (
        round(summary.total_views / summary.total_messages, 2)
        if summary.total_messages
        else 0.0
    )

    return ChannelActivityResponse(
        channel_name=channel_name,
        total_messages=summary.total_messages,
        total_views=summary.total_views,
        avg_views_per_message=avg_views,
        days=[
            DailyActivity(
                activity_date=r.activity_date,
                message_count=r.message_count,
                total_views=r.total_views,
                total_forwards=r.total_forwards,
                images=r.images,
            )
            for r in daily_rows
        ],
    )


# ---------------------------------------------------------------------------
# Endpoint 3 — Message Search
# ---------------------------------------------------------------------------

SEARCH_SQL = """
SELECT
    fm.message_id,
    dc.channel_name,
    dd.full_date::timestamp   AS message_date,
    fm.message_text,
    fm.view_count,
    fm.forward_count,
    fm.has_image
FROM marts.fct_messages fm
JOIN marts.dim_channels dc ON fm.channel_key = dc.channel_key
JOIN marts.dim_dates     dd ON fm.date_key    = dd.date_key
WHERE fm.message_text ILIKE :query
ORDER BY fm.view_count DESC
LIMIT :limit;
"""

COUNT_SQL = """
SELECT COUNT(*) AS total
FROM marts.fct_messages
WHERE message_text ILIKE :query;
"""


@app.get(
    "/api/search/messages",
    response_model=MessageSearchResponse,
    tags=["Search"],
    summary="Full-text keyword search across all messages",
)
def search_messages(
    query: str = Query(..., min_length=2, description="Keyword to search for"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Case-insensitive keyword search across all message text in the warehouse.
    Returns matching messages ranked by view count.
    """
    pattern = f"%{query}%"
    rows = db.execute(text(SEARCH_SQL), {"query": pattern, "limit": limit}).fetchall()
    total = db.execute(text(COUNT_SQL), {"query": pattern}).scalar() or 0

    return MessageSearchResponse(
        query=query,
        limit=limit,
        total_found=total,
        results=[
            MessageItem(
                message_id=r.message_id,
                channel_name=r.channel_name,
                message_date=r.message_date,
                message_text=r.message_text,
                views=r.view_count,
                forwards=r.forward_count,
                has_image=r.has_image,
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# Endpoint 4 — Visual Content Stats
# ---------------------------------------------------------------------------

VISUAL_SQL = """
SELECT
    dc.channel_name,
    COUNT(fm.message_id)                         AS total_messages,
    SUM(fm.has_image::int)                       AS messages_with_images,
    ROUND(
        100.0 * SUM(fm.has_image::int) / NULLIF(COUNT(*),0), 2
    )                                            AS image_rate_pct,
    AVG(CASE WHEN fm.has_image THEN fm.view_count END)  AS avg_views_with_image,
    AVG(CASE WHEN NOT fm.has_image THEN fm.view_count END) AS avg_views_without_image
FROM marts.fct_messages fm
JOIN marts.dim_channels dc ON fm.channel_key = dc.channel_key
GROUP BY dc.channel_name
ORDER BY image_rate_pct DESC;
"""

YOLO_BY_CHANNEL_SQL = """
SELECT
    dc.channel_name,
    SUM(CASE WHEN fid.image_category = 'promotional'     THEN 1 ELSE 0 END) AS promotional,
    SUM(CASE WHEN fid.image_category = 'product_display' THEN 1 ELSE 0 END) AS product_display,
    SUM(CASE WHEN fid.image_category = 'lifestyle'       THEN 1 ELSE 0 END) AS lifestyle,
    SUM(CASE WHEN fid.image_category = 'other'           THEN 1 ELSE 0 END) AS other_cat
FROM marts.fct_image_detections fid
JOIN marts.dim_channels dc ON fid.channel_key = dc.channel_key
GROUP BY dc.channel_name;
"""


@app.get(
    "/api/reports/visual-content",
    response_model=VisualContentResponse,
    tags=["Reports"],
    summary="Image usage and YOLO category breakdown per channel",
)
def visual_content(db: Session = Depends(get_db)):
    """
    Returns per-channel statistics on image usage, including:
    - percentage of posts with images
    - YOLO-derived content categories (promotional, product display, lifestyle, other)
    - average views for image vs. text-only posts
    """
    visual_rows = db.execute(text(VISUAL_SQL)).fetchall()
    yolo_rows = db.execute(text(YOLO_BY_CHANNEL_SQL)).fetchall()

    yolo_map = {
        r.channel_name: {
            "promotional": r.promotional,
            "product_display": r.product_display,
            "lifestyle": r.lifestyle,
            "other": r.other_cat,
        }
        for r in yolo_rows
    }

    channels = []
    for r in visual_rows:
        yc = yolo_map.get(r.channel_name, {})
        channels.append(
            ChannelVisualStats(
                channel_name=r.channel_name,
                total_messages=r.total_messages,
                messages_with_images=r.messages_with_images or 0,
                image_rate_pct=float(r.image_rate_pct or 0),
                promotional=yc.get("promotional", 0),
                product_display=yc.get("product_display", 0),
                lifestyle=yc.get("lifestyle", 0),
                other=yc.get("other", 0),
                avg_views_with_image=round(float(r.avg_views_with_image), 2)
                if r.avg_views_with_image
                else None,
                avg_views_without_image=round(float(r.avg_views_without_image), 2)
                if r.avg_views_without_image
                else None,
            )
        )

    total_msgs = sum(c.total_messages for c in channels) or 1
    total_img = sum(c.messages_with_images for c in channels)
    overall = round(100.0 * total_img / total_msgs, 2)

    return VisualContentResponse(channels=channels, overall_image_rate_pct=overall)


# ---------------------------------------------------------------------------
# Endpoint 5 — Channels List (bonus)
# ---------------------------------------------------------------------------

CHANNELS_LIST_SQL = """
SELECT
    channel_name,
    channel_type,
    total_posts,
    avg_views,
    first_post_date,
    last_post_date
FROM marts.dim_channels
ORDER BY total_posts DESC;
"""


@app.get(
    "/api/channels",
    response_model=ChannelsListResponse,
    tags=["Channels"],
    summary="List all channels in the warehouse",
)
def list_channels(db: Session = Depends(get_db)):
    """Returns all channels with summary statistics from the dim_channels dimension table."""
    rows = db.execute(text(CHANNELS_LIST_SQL)).fetchall()
    return ChannelsListResponse(
        channels=[
            ChannelSummary(
                channel_name=r.channel_name,
                channel_type=r.channel_type,
                total_posts=r.total_posts,
                avg_views=float(r.avg_views or 0),
                first_post_date=r.first_post_date,
                last_post_date=r.last_post_date,
            )
            for r in rows
        ]
    )

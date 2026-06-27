"""
Pydantic schemas for request / response validation.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Top Products
# ---------------------------------------------------------------------------

class TopProductItem(BaseModel):
    term: str
    mention_count: int
    channels: int

class TopProductsResponse(BaseModel):
    items: list[TopProductItem]
    limit: int
    total: int


# ---------------------------------------------------------------------------
# Channel Activity
# ---------------------------------------------------------------------------

class DailyActivity(BaseModel):
    activity_date: date
    message_count: int
    total_views: int
    total_forwards: int
    images: int

class ChannelActivityResponse(BaseModel):
    channel_name: str
    total_messages: int
    total_views: int
    avg_views_per_message: float
    days: list[DailyActivity]


# ---------------------------------------------------------------------------
# Message Search
# ---------------------------------------------------------------------------

class MessageItem(BaseModel):
    message_id: int
    channel_name: str
    message_date: Optional[datetime]
    message_text: str
    views: int
    forwards: int
    has_image: bool

class MessageSearchResponse(BaseModel):
    query: str
    limit: int
    results: list[MessageItem]
    total_found: int


# ---------------------------------------------------------------------------
# Visual Content
# ---------------------------------------------------------------------------

class ChannelVisualStats(BaseModel):
    channel_name: str
    total_messages: int
    messages_with_images: int
    image_rate_pct: float
    promotional: int
    product_display: int
    lifestyle: int
    other: int
    avg_views_with_image: Optional[float]
    avg_views_without_image: Optional[float]

class VisualContentResponse(BaseModel):
    channels: list[ChannelVisualStats]
    overall_image_rate_pct: float


# ---------------------------------------------------------------------------
# Channel list
# ---------------------------------------------------------------------------

class ChannelSummary(BaseModel):
    channel_name: str
    channel_type: Optional[str]
    total_posts: int
    avg_views: float
    first_post_date: Optional[date]
    last_post_date: Optional[date]

class ChannelsListResponse(BaseModel):
    channels: list[ChannelSummary]

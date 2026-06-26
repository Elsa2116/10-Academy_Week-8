"""
Shared pytest fixtures.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def env_defaults(monkeypatch):
    """Ensure environment variables are set for all tests."""
    defaults = {
        "TELEGRAM_API_ID":   "0",
        "TELEGRAM_API_HASH": "test_hash",
        "TELEGRAM_PHONE":    "+251000000000",
        "POSTGRES_HOST":     "localhost",
        "POSTGRES_PORT":     "5432",
        "POSTGRES_DB":       "medical_warehouse_test",
        "POSTGRES_USER":     "test_user",
        "POSTGRES_PASSWORD": "test_pass",
    }
    for k, v in defaults.items():
        monkeypatch.setenv(k, os.getenv(k, v))


@pytest.fixture
def sample_message():
    return {
        "message_id":   1001,
        "channel_name": "TestChannel",
        "message_date": "2024-03-15T10:30:00+00:00",
        "message_text": "Paracetamol 500mg — 45 ETB",
        "has_media":    True,
        "is_photo":     True,
        "image_path":   "data/raw/images/TestChannel/1001.jpg",
        "views":        350,
        "forwards":     12,
        "scraped_at":   "2024-03-15T11:00:00+00:00",
    }


@pytest.fixture
def sample_json_lake(tmp_path, sample_message):
    """Create a minimal data lake structure for loader tests."""
    day_dir = tmp_path / "2024-03-15"
    day_dir.mkdir()
    json_file = day_dir / "TestChannel.json"
    json_file.write_text(json.dumps([sample_message]))
    return tmp_path

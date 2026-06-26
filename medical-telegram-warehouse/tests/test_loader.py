"""
Unit tests for the raw data loader.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCollectRecords:
    def test_empty_data_lake(self, tmp_path, monkeypatch):
        """When no JSON files exist, collect_records returns an empty list."""
        import src.loader as loader_module

        monkeypatch.setattr(
            loader_module.settings, "messages_dir", tmp_path
        )
        rows = loader_module._collect_records()
        assert rows == []

    def test_collects_all_records(self, tmp_path, monkeypatch):
        """Records from multiple JSON files are all collected."""
        import src.loader as loader_module

        monkeypatch.setattr(
            loader_module.settings, "messages_dir", tmp_path
        )
        data = [
            {
                "message_id": 1,
                "channel_name": "TestChannel",
                "message_date": "2024-01-15T10:00:00+00:00",
                "message_text": "Paracetamol 500mg available",
                "has_media": False,
                "is_photo": False,
                "image_path": None,
                "views": 120,
                "forwards": 5,
                "scraped_at": "2024-01-16T00:00:00+00:00",
            }
        ]
        json_file = tmp_path / "2024-01-15" / "TestChannel.json"
        json_file.parent.mkdir(parents=True)
        json_file.write_text(json.dumps(data))

        rows = loader_module._collect_records()
        assert len(rows) == 1
        msg_id, channel, *_ = rows[0]
        assert msg_id == 1
        assert channel == "TestChannel"

    def test_missing_optional_fields_default_to_zero(self, tmp_path, monkeypatch):
        """Missing views/forwards default to 0, not null."""
        import src.loader as loader_module

        monkeypatch.setattr(
            loader_module.settings, "messages_dir", tmp_path
        )
        data = [
            {
                "message_id": 99,
                "channel_name": "MinimalChannel",
                "message_date": "2024-03-01T08:00:00+00:00",
                "message_text": "Hello",
            }
        ]
        json_file = tmp_path / "minimal.json"
        json_file.write_text(json.dumps(data))

        rows = loader_module._collect_records()
        assert len(rows) == 1
        row = rows[0]
        # views is index 8, forwards index 9
        assert row[8] == 0
        assert row[9] == 0

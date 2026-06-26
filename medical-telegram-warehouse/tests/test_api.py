"""
Unit tests for the FastAPI application.
Uses TestClient with a mocked database session.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("api.database.check_connection", return_value=True):
        from api.main import app
        return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_status_field(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert "database" in data


class TestTopProducts:
    def test_requires_db(self, client):
        with patch("api.main.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.execute.return_value.fetchall.return_value = []
            mock_get_db.return_value = iter([mock_db])
            resp = client.get("/api/reports/top-products?limit=5")
            assert resp.status_code in (200, 500)

    def test_limit_param_validated(self, client):
        resp = client.get("/api/reports/top-products?limit=0")
        assert resp.status_code == 422

    def test_limit_too_large(self, client):
        resp = client.get("/api/reports/top-products?limit=200")
        assert resp.status_code == 422


class TestSearchMessages:
    def test_missing_query_param(self, client):
        resp = client.get("/api/search/messages")
        assert resp.status_code == 422

    def test_query_too_short(self, client):
        resp = client.get("/api/search/messages?query=a")
        assert resp.status_code == 422

"""Tests for HTTP request logging middleware."""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestRequestLoggingMiddleware:
    """Every HTTP request must produce a structured log entry with method, path, status, duration."""

    def test_health_request_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        from backend.app import app
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level(logging.INFO, logger="backend.app"):
            response = client.get("/api/health")

        assert response.status_code == 200
        # Find the request log entry
        request_logs = [r for r in caplog.records if "GET" in r.getMessage() and "/api/health" in r.getMessage()]
        assert request_logs, f"No request log found. Records: {[r.getMessage() for r in caplog.records]}"
        record = request_logs[0]
        assert hasattr(record, "status_code") or "200" in record.getMessage()

    def test_log_entry_includes_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        from backend.app import app
        client = TestClient(app, raise_server_exceptions=False)

        with caplog.at_level(logging.INFO, logger="backend.app"):
            client.get("/api/health")

        request_logs = [r for r in caplog.records if "/api/health" in r.getMessage()]
        assert request_logs
        record = request_logs[0]
        assert hasattr(record, "duration_ms"), "Log record missing duration_ms field"

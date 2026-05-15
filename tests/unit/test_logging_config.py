"""Tests for backend.logging_config — structured logging setup."""
from __future__ import annotations

import json
import logging
import io

import pytest


class TestLoggingConfig:
    """setup_logging() must configure a JSON-line structured logger."""

    def test_setup_logging_returns_logger(self) -> None:
        from backend.logging_config import setup_logging
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_log_output_is_valid_json(self) -> None:
        from backend.logging_config import setup_logging, StructuredFormatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("test_json_output")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)

        logger.info("test message", extra={"job_id": "job-123"})

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["message"] == "test message"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_structured_formatter_includes_extra_fields(self) -> None:
        from backend.logging_config import StructuredFormatter
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("test_extra_fields")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)

        logger.info("job started", extra={"job_id": "job-abc", "duration_ms": 42})

        parsed = json.loads(stream.getvalue().strip())
        assert parsed.get("job_id") == "job-abc"
        assert parsed.get("duration_ms") == 42

    def test_setup_logging_respects_log_level_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from backend import logging_config
        import importlib
        importlib.reload(logging_config)
        logger = logging_config.setup_logging()
        assert logger.level == logging.DEBUG

"""Structured logging setup for the capstone backend.

All log output is JSON lines to stdout, suitable for Render.com log aggregation.
File rotation is also configured for local development.

Usage:
    from backend.logging_config import setup_logging
    setup_logging()   # call once at startup

    import logging
    logger = logging.getLogger(__name__)
    logger.info("job started", extra={"job_id": "job-abc", "duration_ms": 123})
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include any extra fields passed via extra={...}
        skip = logging.LogRecord.__dict__.keys() | {
            "message", "asctime", "exc_info", "exc_text", "stack_info",
            "taskName",  # Python 3.12+
        }
        for key, value in record.__dict__.items():
            if key not in skip and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=True)


def setup_logging() -> logging.Logger:
    """Configure and return the root logger with structured JSON output.

    Log level is controlled by the LOG_LEVEL environment variable (default: INFO).
    Logs go to stdout and, in the project root's logs/ directory, to a rotating file.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if called more than once
    if root.handlers:
        return root

    formatter = StructuredFormatter()

    # stdout handler — primary output on Render
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # Rotating file handler — useful for local debugging
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "capstone.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    return root

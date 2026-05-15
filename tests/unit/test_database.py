"""Tests for backend.database — connection management and rollback behaviour."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.database import get_connection


class TestGetConnectionRollback:
    """get_connection must explicitly rollback uncommitted changes on exception."""

    def test_commits_on_success(self, tmp_db: Path) -> None:
        with patch("backend.database.settings") as mock:
            mock.database_path = tmp_db
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, "
                    "result_run_dir, error_message, created_at, updated_at) "
                    "VALUES ('j1', NULL, 'augment', 'queued', NULL, NULL, NULL, 'now', 'now')"
                )

        # Verify the row was committed
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM jobs WHERE job_id = 'j1'").fetchone()[0]
        assert count == 1

    def test_rolls_back_on_exception(self, tmp_db: Path) -> None:
        with patch("backend.database.settings") as mock:
            mock.database_path = tmp_db
            with pytest.raises(RuntimeError):
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, "
                        "result_run_dir, error_message, created_at, updated_at) "
                        "VALUES ('j2', NULL, 'augment', 'queued', NULL, NULL, NULL, 'now', 'now')"
                    )
                    raise RuntimeError("simulated failure")

        # The INSERT must have been rolled back
        with sqlite3.connect(tmp_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM jobs WHERE job_id = 'j2'").fetchone()[0]
        assert count == 0

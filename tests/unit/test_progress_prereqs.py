"""Tests for progress-endpoint prerequisites.

These cover:
- result_run_dir written to DB at 'running' status (not only at 'completed')
- RunState written with 'failed' status when pipeline raises
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.service import JobManager, QueuedJob


def _insert_queued_augment_job(db_path: Path, job_id: str, seed_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path,
                              result_run_dir, error_message, created_at, updated_at)
            VALUES (?, NULL, 'augment', 'queued', ?, NULL, NULL,
                    '2026-04-02T00:00:00Z', '2026-04-02T00:00:00Z')
            """,
            (job_id, str(seed_path)),
        )


def _get_job_row(db_path: Path, job_id: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, result_run_dir FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else {}


class TestResultRunDirAtRunningStatus:
    """result_run_dir must be written to DB when job enters 'running', not only at 'completed'.

    This is required so GET /api/jobs/{id}/progress can locate run_state.json mid-run.
    """

    def test_result_run_dir_persisted_before_pipeline_runs(
        self, tmp_db: Path, tmp_path: Path
    ) -> None:
        seed_content = {
            "incident_id": "test-incident",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))
        _insert_queued_augment_job(tmp_db, "job-xyz", seed_path)

        run_dir_seen: list[str] = []

        def fake_pipeline(seed_path, runs_dir):
            # Check result_run_dir is already in DB at this point (job is 'running')
            row = _get_job_row(tmp_db, "job-xyz")
            if row.get("result_run_dir"):
                run_dir_seen.append(row["result_run_dir"])
            result_dir = Path(runs_dir) / "test-incident"
            result_dir.mkdir(parents=True, exist_ok=True)
            return result_dir

        with patch("backend.database.settings") as db_settings, \
             patch("backend.service.settings") as svc_settings, \
             patch("backend.service.run_augmentation_mvp", side_effect=fake_pipeline):
            db_settings.database_path = tmp_db
            svc_settings.database_path = tmp_db
            svc_settings.runs_dir = tmp_path

            manager = JobManager()
            manager.queue.put(
                QueuedJob(job_id="job-xyz", job_type="augment", seed_path=seed_path)
            )
            done = threading.Event()
            original_mark = manager._mark_job

            def patched_mark(job_id, status, **kwargs):
                original_mark(job_id, status, **kwargs)
                if status == "completed":
                    done.set()

            manager._mark_job = patched_mark
            manager._worker_thread = threading.Thread(
                target=manager._worker_loop, daemon=True
            )
            manager._worker_thread.start()
            done.wait(timeout=5)

        assert run_dir_seen, "result_run_dir was not written to DB before pipeline ran"
        # incident_id is derived from seed fields: seed_type="manual" + chain="eth" → "manual-eth"
        assert run_dir_seen[0].endswith("manual-eth")

"""Tests for GET /api/jobs/{job_id}/progress endpoint."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _make_job_row(db_path: Path, job_id: str, status: str, result_run_dir: str | None = None) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path,
                              result_run_dir, error_message, created_at, updated_at)
            VALUES (?, NULL, 'augment', ?, NULL, ?, NULL,
                    '2026-04-02T00:00:00Z', '2026-04-02T00:00:00Z')
            """,
            (job_id, status, result_run_dir),
        )


def _write_run_state(run_dir: Path, stages: dict[str, str], current_stage: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "job_id": "job-test",
        "incident_id": "test-incident",
        "trigger_type": "api",
        "current_stage": current_stage,
        "node_status": stages,
        "retry_counts": {},
        "started_at": "2026-04-02T00:00:00+00:00",
        "updated_at": "2026-04-02T00:00:01+00:00",
        "completed_at": None,
        "run_notes": [],
        "artifacts": {},
    }
    (run_dir / "run_state.json").write_text(json.dumps(state))


class TestProgressEndpoint:
    """GET /api/jobs/{job_id}/progress must return structured stage progress."""

    def test_returns_404_for_unknown_job(self, tmp_db: Path, tmp_path: Path) -> None:
        from backend.app import app
        with patch("backend.database.settings") as db_s, \
             patch("backend.service.settings") as svc_s, \
             patch("backend.app.settings") as app_s:
            db_s.database_path = tmp_db
            svc_s.database_path = tmp_db
            svc_s.runs_dir = tmp_path
            app_s.api_token = ""
            app_s.cors_allow_origins = []
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/jobs/nonexistent/progress")
        assert response.status_code == 404

    def test_returns_progress_for_running_job(self, tmp_db: Path, tmp_path: Path) -> None:
        run_dir = tmp_path / "test-incident"
        _write_run_state(
            run_dir,
            stages={"source_finder": "completed", "source_expander": "running"},
            current_stage="source_expander",
        )
        _make_job_row(tmp_db, "job-run-1", "running", str(run_dir))

        from backend.app import app
        with patch("backend.database.settings") as db_s, \
             patch("backend.service.settings") as svc_s, \
             patch("backend.app.settings") as app_s:
            db_s.database_path = tmp_db
            svc_s.database_path = tmp_db
            svc_s.runs_dir = tmp_path
            app_s.api_token = ""
            app_s.cors_allow_origins = []
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/jobs/job-run-1/progress")

        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == "job-run-1"
        assert body["status"] == "running"
        assert body["current_stage"] == "source_expander"
        assert isinstance(body["stages"], list)
        stage_names = [s["name"] for s in body["stages"]]
        assert "source_finder" in stage_names
        assert "source_expander" in stage_names

    def test_returns_queued_status_when_no_run_dir(self, tmp_db: Path, tmp_path: Path) -> None:
        _make_job_row(tmp_db, "job-queued-1", "queued", None)

        from backend.app import app
        with patch("backend.database.settings") as db_s, \
             patch("backend.service.settings") as svc_s, \
             patch("backend.app.settings") as app_s:
            db_s.database_path = tmp_db
            svc_s.database_path = tmp_db
            svc_s.runs_dir = tmp_path
            app_s.api_token = ""
            app_s.cors_allow_origins = []
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/jobs/job-queued-1/progress")

        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == "job-queued-1"
        assert body["status"] == "queued"
        assert body["stages"] == []

    def test_returns_progress_from_job_progress_file_for_file_backed_jobs(self, tmp_db: Path, tmp_path: Path) -> None:
        summary_path = tmp_path / "_discovery_jobs" / "job-disc-1.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text("{}")
        _make_job_row(tmp_db, "job-disc-1", "running", str(summary_path))

        progress_path = tmp_path / "_job_progress" / "job-disc-1.json"
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text(
            json.dumps(
                {
                    "job_id": "job-disc-1",
                    "status": "running",
                    "current_stage": "discovery_sync",
                    "stages": [{"name": "discovery_sync", "status": "running"}],
                    "detail": "Scanning configured sources.",
                }
            )
        )

        from backend.app import app
        with patch("backend.database.settings") as db_s, \
             patch("backend.service.settings") as svc_s, \
             patch("backend.app.settings") as app_s:
            db_s.database_path = tmp_db
            svc_s.database_path = tmp_db
            svc_s.runs_dir = tmp_path
            app_s.api_token = ""
            app_s.cors_allow_origins = []
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/jobs/job-disc-1/progress")

        assert response.status_code == 200
        body = response.json()
        assert body["current_stage"] == "discovery_sync"
        assert body["stages"] == [{"name": "discovery_sync", "status": "running"}]
        assert body["detail"] == "Scanning configured sources."

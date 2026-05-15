from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _insert_schedule(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO schedules (schedule_name, job_type, status, interval_seconds, payload_json, last_enqueued_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "daily_discovery",
                "discovery",
                "active",
                21600,
                json.dumps(
                    {
                        "sources": ["slowmist", "web3sec", "external_explorer", "defihacklabs"],
                        "execute_augmentation": True,
                    }
                ),
                "1712102400",
            ),
        )


def _write_publishable_run(run_dir: Path, trigger_type: str, title: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "incident_library_entry.json").write_text(
        json.dumps(
            {
                "incident_id": run_dir.name,
                "title": title,
                "chain": "Arbitrum",
                "summary": "Incident summary",
                "status": "published_brief",
                "completeness_score": 0.75,
            }
        )
    )
    (run_dir / "run_state.json").write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "incident_id": run_dir.name,
                "trigger_type": trigger_type,
                "current_stage": "completed",
                "node_status": {},
                "retry_counts": {},
                "started_at": "2026-04-03T00:00:00+00:00",
                "updated_at": "2026-04-03T00:00:01+00:00",
                "completed_at": "2026-04-03T00:00:02+00:00",
                "run_notes": [],
                "artifacts": {},
            }
        )
    )


def test_discovery_overview_reports_schedule_latest_run_and_gap(tmp_db: Path, tmp_path: Path) -> None:
    _insert_schedule(tmp_db)
    _write_publishable_run(tmp_path / "paribus-arbitrum-2025-01-18", "demo_corpus", "Paribus")
    _write_publishable_run(tmp_path / "new-auto-incident", "discovery_sync", "Fresh Auto Incident")

    summary_dir = tmp_path / "_discovery_jobs"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "job-disc-123.json").write_text(
        json.dumps(
            {
                "source_count": 4,
                "record_count": 12,
                "incident_count": 3,
                "seed_paths": ["a.json", "b.json", "c.json"],
                "run_dirs": ["run-a", "run-b", "run-c"],
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
        response = client.get("/api/discovery/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["schedule"]["configured"] is True
    assert body["monitored_sources"] == ["slowmist", "web3sec", "external_explorer", "defihacklabs"]
    assert body["latest_discovery_run"]["incident_count"] == 3
    assert body["incident_origin_breakdown"]["demo_corpus"] == 1
    assert body["incident_origin_breakdown"]["discovery_sync"] == 1

"""Tests for JobManager — queue rehydration and job lifecycle."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.service import JobManager, QueuedJob


def _insert_queued_job(db_path: Path, job_id: str, job_type: str, seed_path: str | None = None) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path,
                              result_run_dir, error_message, created_at, updated_at)
            VALUES (?, NULL, ?, 'queued', ?, NULL, NULL, '2026-04-02T00:00:00Z', '2026-04-02T00:00:00Z')
            """,
            (job_id, job_type, seed_path),
        )


class TestQueueRehydration:
    """JobManager._rehydrate_queue() must pick up stranded queued jobs on startup."""

    def test_rehydrates_augment_jobs_from_db(self, tmp_db: Path, tmp_path: Path) -> None:
        seed = tmp_path / "seed.json"
        seed.write_text('{"incident_id": "test"}')
        _insert_queued_job(tmp_db, "job-aaa", "augment", str(seed))
        _insert_queued_job(tmp_db, "job-bbb", "augment", str(seed))

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings:
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            manager._rehydrate_queue()

        assert manager.queue.qsize() == 2

    def test_rehydrates_discovery_jobs_from_db(self, tmp_db: Path, tmp_path: Path) -> None:
        _insert_queued_job(tmp_db, "job-disc-1", "discovery")

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings:
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            manager._rehydrate_queue()

        queued: list[QueuedJob] = []
        while not manager.queue.empty():
            queued.append(manager.queue.get_nowait())

        assert len(queued) == 1
        assert queued[0].job_id == "job-disc-1"
        assert queued[0].job_type == "discovery"

    def test_ignores_non_queued_jobs(self, tmp_db: Path, tmp_path: Path) -> None:
        """Jobs with status running/completed/failed must not be re-enqueued."""
        for status in ("running", "completed", "failed"):
            with sqlite3.connect(tmp_db) as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path,
                                      result_run_dir, error_message, created_at, updated_at)
                    VALUES (?, NULL, 'augment', ?, NULL, NULL, NULL,
                            '2026-04-02T00:00:00Z', '2026-04-02T00:00:00Z')
                    """,
                    (f"job-{status}", status),
                )

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings:
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            manager._rehydrate_queue()

        assert manager.queue.qsize() == 1

    def test_start_calls_rehydrate(self, tmp_db: Path, tmp_path: Path) -> None:
        """start() must call _rehydrate_queue() so orphaned jobs are recovered."""
        seed = tmp_path / "seed.json"
        seed.write_text('{"incident_id": "test"}')
        _insert_queued_job(tmp_db, "job-orphan", "augment", str(seed))

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings:
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            # Patch worker/scheduler so they don't actually process jobs
            with patch.object(manager, "_worker_loop"), patch.object(manager, "_scheduler_loop"):
                manager.start()

        assert manager.queue.qsize() == 1


class TestJobProgressFiles:
    def test_write_job_progress_creates_file(self, tmp_db: Path, tmp_path: Path) -> None:
        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings:
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            manager.write_job_progress(
                "job-progress-1",
                status="running",
                current_stage="discovery_sync",
                stages=[{"name": "discovery_sync", "status": "running"}],
                detail="Discovery is in progress.",
            )

        progress_path = tmp_path / "_job_progress" / "job-progress-1.json"
        assert progress_path.exists()
        payload = progress_path.read_text()
        assert "discovery_sync" in payload
        assert "Discovery is in progress." in payload


class TestPublishableIncidentFilter:
    def test_list_incidents_excludes_synthetic_entries(self, tmp_db: Path, tmp_path: Path) -> None:
        real_run = tmp_path / "real-incident"
        real_run.mkdir(parents=True, exist_ok=True)
        (real_run / "incident_library_entry.json").write_text(
            json.dumps(
                {
                    "incident_id": "real-incident",
                    "title": "Caterpiller Coin",
                    "chain": "BSC",
                    "summary": "Real incident",
                    "status": "published_brief",
                    "completeness_score": 0.88,
                }
            )
        )

        synthetic_run = tmp_path / "playwright-demo-incident-base"
        synthetic_run.mkdir(parents=True, exist_ok=True)
        (synthetic_run / "incident_library_entry.json").write_text(
            json.dumps(
                {
                    "incident_id": "playwright-demo-incident-base",
                    "title": "Playwright Demo Incident",
                    "chain": "Base",
                    "summary": "Synthetic incident",
                    "status": "published_brief",
                    "completeness_score": 0.12,
                }
            )
        )

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings, \
             patch("backend.service.REPO_ROOT", tmp_path / "empty_repo"):
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            incidents = manager.list_incidents()

        assert [incident["incident_id"] for incident in incidents] == ["real-incident"]

    def test_discovery_leads_are_merged_into_library_when_discovery_history_exists(self, tmp_db: Path, tmp_path: Path) -> None:
        discovery_dir = tmp_path / "_discovery_jobs"
        discovery_dir.mkdir(parents=True, exist_ok=True)
        (discovery_dir / "job-disc-1.json").write_text("{}")

        with patch("backend.database.settings") as mock_settings, \
             patch("backend.service.settings") as mock_svc_settings, \
             patch("backend.service.REPO_ROOT", tmp_path / "empty_repo"):
            mock_settings.database_path = tmp_db
            mock_svc_settings.database_path = tmp_db
            mock_svc_settings.runs_dir = tmp_path
            manager = JobManager()
            manager.list_discovery_leads = lambda limit=40: [  # type: ignore[method-assign]
                {
                    "incident_id": "historic-auto-lead",
                    "title": "Historic Auto Lead",
                    "protocol_name": "Historic Auto Lead",
                    "chain": "Ethereum",
                    "incident_date": "2025-01-10",
                    "summary": "Auto-collected discovery lead.",
                    "status": "auto_collected_lead",
                    "completeness_score": 0.24,
                    "source_count": 2,
                    "direct_source_count": 2,
                    "secondary_source_count": 0,
                    "social_count": 0,
                    "poc_count": 0,
                    "explorer_count": 1,
                    "report_count": 2,
                    "missing_fields": [],
                    "last_updated": "2025-01-10",
                    "pattern_label": "price_manipulation",
                    "attack_tx_hashes": [],
                    "source_preview": ["https://example.com/a", "https://example.com/b"],
                }
            ]
            incidents = manager.list_incidents()

        assert [incident["incident_id"] for incident in incidents] == ["historic-auto-lead"]

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from incident_augmentation.demo_corpus import build_demo_corpus
from incident_augmentation.discovery import collect_records, group_records_to_incidents, run_discovery_sync
from incident_augmentation.models import utc_now_iso
from incident_augmentation.pipeline import load_seed, normalize_completeness_score, run_augmentation_mvp
from incident_augmentation.analyst_report import build_analyst_report
from incident_augmentation.source_snapshot_index import (
    HISTORY_CACHE_NAME,
    build_primary_source_history_index,
    read_history_cache,
    write_history_cache,
)

from .config import settings
from .database import ensure_database, get_connection

logger = logging.getLogger(__name__)

# Fixture runs directory (inside Docker image at /app/data/fixtures/runs)
_FIXTURE_RUNS_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "runs"


def _backfill_pipeline_trace(incident_id: str, technical_analysis: dict) -> dict:
    """If technical_analysis lacks pipeline_trace (or has an empty one), try to
    inject it from the matching fixture file.  Returns the (possibly updated) dict.
    This is an in-memory fallback so the API always returns pipeline_trace even
    when the on-disk file hasn't been patched yet.
    """
    if not isinstance(technical_analysis, dict):
        return technical_analysis
    existing = technical_analysis.get("pipeline_trace")
    if isinstance(existing, dict) and existing.get("records"):
        return technical_analysis  # already populated, nothing to do

    fixture_ta = _FIXTURE_RUNS_DIR / incident_id / "technical_analysis.json"
    if not fixture_ta.exists():
        return technical_analysis
    try:
        fixture_data = json.loads(fixture_ta.read_text())
        pt = fixture_data.get("pipeline_trace")
        if isinstance(pt, dict) and pt.get("records"):
            return {**technical_analysis, "pipeline_trace": pt}
    except Exception:  # noqa: BLE001
        pass
    return technical_analysis
REPO_ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_INCIDENT_MARKERS = (
    "playwright",
    "async-demo",
    "demo-missing-id",
    "sample",
)


@dataclass
class QueuedJob:
    job_id: str
    job_type: str
    seed_path: Path | None = None
    incident_id: str | None = None
    payload: dict | None = None


class JobManager:
    def __init__(self) -> None:
        ensure_database()
        self.queue: queue.Queue[QueuedJob] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._discovery_leads_cache: list[dict] = []
        self._discovery_leads_cached_at = 0.0

    def start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._rehydrate_queue()
        self._cleanup_old_runs()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._worker_thread.start()
        self._scheduler_thread.start()

    def _cleanup_old_runs(self, max_age_days: int = 30) -> None:
        """Delete completed run folders older than max_age_days to prevent unbounded disk growth."""
        _SKIP_DIRS = {"_job_progress", "_queue_inputs", "_discovery_jobs", "discovery_seeds", "_demo_seed_inputs"}
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        runs_dir = settings.runs_dir
        if not runs_dir.exists():
            return
        with get_connection() as connection:
            active_dirs = {
                row["result_run_dir"]
                for row in connection.execute(
                    "SELECT result_run_dir FROM jobs WHERE status IN ('running', 'queued') AND result_run_dir IS NOT NULL"
                ).fetchall()
            }
        deleted = 0
        for entry in runs_dir.iterdir():
            if not entry.is_dir() or entry.name in _SKIP_DIRS:
                continue
            if str(entry) in active_dirs:
                continue
            mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
                deleted += 1
        if deleted:
            logger.info("runs.cleanup", extra={"deleted_count": deleted})

    def _rehydrate_queue(self) -> None:
        """Re-enqueue any jobs that were left in 'queued' or interrupted 'running' status from a previous run."""
        with get_connection() as connection:
            stuck = connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'running'"
            ).fetchone()[0]
            if stuck:
                logger.warning("job.recovery", extra={"stuck_running_count": stuck})
                connection.execute(
                    "UPDATE jobs SET status = 'queued', updated_at = ? WHERE status = 'running'",
                    (utc_now_iso(),),
                )
            rows = connection.execute(
                """
                SELECT job_id, job_type, seed_path, incident_id
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                """
            ).fetchall()
        count = len(rows)
        if count:
            logger.info("queue.rehydrated", extra={"rehydrated_count": count})
        for row in rows:
            self.queue.put(
                QueuedJob(
                    job_id=row["job_id"],
                    job_type=row["job_type"],
                    seed_path=Path(row["seed_path"]) if row["seed_path"] else None,
                    incident_id=row["incident_id"],
                )
            )

    def stop(self) -> None:
        self._stop_event.set()

    def job_progress_path(self, job_id: str) -> Path:
        return settings.runs_dir / "_job_progress" / f"{job_id}.json"

    def write_job_progress(
        self,
        job_id: str,
        *,
        status: str,
        current_stage: str | None,
        stages: list[dict[str, str]] | None = None,
        detail: str | None = None,
    ) -> None:
        path = self.job_progress_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": job_id,
            "status": status,
            "current_stage": current_stage,
            "stages": stages or [],
            "detail": detail,
            "updated_at": utc_now_iso(),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")

    def enqueue_augmentation(self, seed_payload: dict) -> str:
        now = utc_now_iso()
        incident_id = seed_payload.get("incident_id") or seed_payload.get("incident_name") or "incident"
        job_id = seed_payload.get("job_id") or f"job-{uuid4().hex[:12]}"
        seed_path = settings.runs_dir / "_queue_inputs" / f"{job_id}.json"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(json.dumps(seed_payload, indent=2, ensure_ascii=True) + "\n")

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, result_run_dir, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, seed_payload.get("incident_id"), "augment", "queued", str(seed_path), None, None, now, now),
            )

        self.queue.put(
            QueuedJob(
                job_id=job_id,
                job_type="augment",
                seed_path=seed_path,
                incident_id=seed_payload.get("incident_id"),
            )
        )
        return job_id

    def list_jobs(self) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT job_id, incident_id, job_type, status, seed_path, result_run_dir, error_message, created_at, updated_at
                FROM jobs
                ORDER BY created_at DESC
                LIMIT 50
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def enqueue_discovery(self, payload: dict | None = None) -> str:
        now = utc_now_iso()
        job_id = f"job-{uuid4().hex[:12]}"
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, result_run_dir, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, None, "discovery", "queued", None, None, None, now, now),
            )
        self.queue.put(QueuedJob(job_id=job_id, job_type="discovery", payload=payload or {}))
        return job_id

    def enqueue_demo_corpus(self) -> str:
        now = utc_now_iso()
        job_id = f"job-{uuid4().hex[:12]}"
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, result_run_dir, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, None, "demo_corpus", "queued", None, None, None, now, now),
            )
        self.queue.put(QueuedJob(job_id=job_id, job_type="demo_corpus"))
        return job_id

    def latest_dashboard_view(self) -> dict | None:
        run_dirs = [path for path in settings.runs_dir.iterdir() if path.is_dir() and not path.name.startswith("_")] if settings.runs_dir.exists() else []
        candidates: list[tuple[float, Path]] = []
        for run_dir in run_dirs:
            dashboard_path = run_dir / "dashboard_view.json"
            if dashboard_path.exists():
                payload = json.loads(dashboard_path.read_text())
                if self._is_publishable_incident(
                    incident_id=payload.get("incident_id", run_dir.name),
                    title=payload.get("card", {}).get("title", ""),
                ):
                    candidates.append((dashboard_path.stat().st_mtime, dashboard_path))
        if not candidates:
            return None
        latest_path = max(candidates, key=lambda item: item[0])[1]
        payload = json.loads(latest_path.read_text())
        card = payload.get("card", {})
        card["completeness_score"] = normalize_completeness_score(card.get("completeness_score", 0))
        payload["card"] = card
        return payload

    def latest_augmented_incident(self) -> dict | None:
        run_dirs = [path for path in settings.runs_dir.iterdir() if path.is_dir() and not path.name.startswith("_")] if settings.runs_dir.exists() else []
        candidates: list[tuple[float, Path]] = []
        for run_dir in run_dirs:
            incident_path = run_dir / "augmented_incident.json"
            if incident_path.exists():
                payload = json.loads(incident_path.read_text())
                if self._is_publishable_incident(
                    incident_id=payload.get("incident_id", run_dir.name),
                    title=payload.get("title", ""),
                ):
                    candidates.append((incident_path.stat().st_mtime, incident_path))
        if not candidates:
            return None
        latest_path = max(candidates, key=lambda item: item[0])[1]
        payload = json.loads(latest_path.read_text())
        quality = payload.get("quality_report", {})
        quality["completeness_score"] = normalize_completeness_score(quality.get("completeness_score", 0))
        payload["quality_report"] = quality
        return payload

    def list_incidents(self) -> list[dict]:
        run_dirs = [path for path in settings.runs_dir.iterdir() if path.is_dir() and not path.name.startswith("_")] if settings.runs_dir.exists() else []
        entries: list[tuple[float, dict]] = []
        for run_dir in run_dirs:
            entry_path = run_dir / "incident_library_entry.json"
            dashboard_path = run_dir / "dashboard_view.json"
            if entry_path.exists():
                payload = json.loads(entry_path.read_text())
                if self._is_publishable_incident(
                    incident_id=payload.get("incident_id", run_dir.name),
                    title=payload.get("title", ""),
                ):
                    entries.append((entry_path.stat().st_mtime, payload))
            elif dashboard_path.exists():
                dashboard = json.loads(dashboard_path.read_text())
                if self._is_publishable_incident(
                    incident_id=dashboard.get("incident_id", run_dir.name),
                    title=dashboard.get("card", {}).get("title", ""),
                ):
                    entries.append(
                        (
                            dashboard_path.stat().st_mtime,
                            {
                                "incident_id": dashboard["incident_id"],
                                "title": dashboard["card"]["title"],
                                "protocol_name": dashboard["card"].get("protocol_name", ""),
                                "chain": dashboard["card"].get("chain", "unknown"),
                                "incident_date": dashboard["card"].get("incident_date", ""),
                                "summary": dashboard["card"].get("summary", ""),
                                "status": dashboard.get("status", "unknown"),
                                "completeness_score": dashboard["card"].get("completeness_score", 0),
                                "source_count": dashboard["card"].get("source_count", 0),
                                "direct_source_count": dashboard["card"].get("direct_source_count", 0),
                                "secondary_source_count": dashboard["card"].get("secondary_source_count", 0),
                                "missing_fields": dashboard["detail"].get("missing_fields", []),
                                "last_updated": dashboard.get("last_updated", ""),
                                "pattern_label": "",
                                "attack_tx_hashes": [],
                                "source_preview": [],
                            },
                        )
                    )
        normalized_entries = [entry for _, entry in sorted(entries, key=lambda item: item[0], reverse=True)]
        for entry in normalized_entries:
            entry["completeness_score"] = normalize_completeness_score(entry.get("completeness_score", 0))
        discovery_entries = self.list_discovery_leads(limit=120)
        historical_entries = self.list_historical_source_leads(limit=120)
        merged: list[dict] = []
        seen_keys: set[str] = set()
        # Prefer fully built run outputs over lightweight discovery/history leads.
        # The previous merge order let 24%-complete lead cards shadow richer dossiers
        # that shared the same title and incident date.
        for entry in [*normalized_entries, *discovery_entries, *historical_entries]:
            title = (entry.get("title") or entry.get("protocol_name") or "").strip().lower()
            incident_date = (entry.get("incident_date") or "").strip()
            key = f"{title}::{incident_date}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(entry)
        merged.sort(
            key=lambda item: (
                item.get("incident_date", ""),
                normalize_completeness_score(item.get("completeness_score", 0)),
            ),
            reverse=True,
        )
        return merged

    def get_incident_bundle(self, incident_id: str) -> dict | None:
        run_dir = settings.runs_dir / incident_id
        if not run_dir.exists():
            return self._build_bundle_from_discovery_lead(incident_id)
        files = {
            "incident_library_entry": run_dir / "incident_library_entry.json",
            "dashboard_view": run_dir / "dashboard_view.json",
            "augmented_incident": run_dir / "augmented_incident.json",
            "source_index": run_dir / "source_index.json",
            "source_documents": run_dir / "source_documents.json",
            "quality_report": run_dir / "quality_report.json",
            "technical_analysis": run_dir / "technical_analysis.json",
            "run_state": run_dir / "run_state.json",
            "run_events": run_dir / "run_events.json",
            "agent_trace": run_dir / "agent_trace.json",
            "report_inputs": run_dir / "report_inputs.json",
            "analyst_report": run_dir / "analyst_report.json",
        }
        payload: dict[str, object] = {"incident_id": incident_id}
        for key, path in files.items():
            if path.exists():
                payload[key] = json.loads(path.read_text())
        # Backfill pipeline_trace in-memory if the on-disk file is missing it
        ta = payload.get("technical_analysis")
        if isinstance(ta, dict):
            payload["technical_analysis"] = _backfill_pipeline_trace(incident_id, ta)
        entry = payload.get("incident_library_entry", {})
        augmented = payload.get("augmented_incident", {})
        if not self._is_publishable_incident(
            incident_id=incident_id,
            title=str(entry.get("title") or augmented.get("title") or ""),
        ):
            return None
        quality_report = payload.get("quality_report", {})
        if isinstance(quality_report, dict):
            quality_report["completeness_score"] = normalize_completeness_score(quality_report.get("completeness_score", 0))
            payload["quality_report"] = quality_report
        if isinstance(entry, dict):
            entry["completeness_score"] = normalize_completeness_score(entry.get("completeness_score", 0))
            payload["incident_library_entry"] = entry
        if isinstance(augmented, dict):
            augmented_quality = augmented.get("quality_report", {})
            if isinstance(augmented_quality, dict):
                augmented_quality["completeness_score"] = normalize_completeness_score(augmented_quality.get("completeness_score", 0))
                augmented["quality_report"] = augmented_quality
            payload["augmented_incident"] = augmented
        if "analyst_report" not in payload and isinstance(augmented, dict) and isinstance(payload.get("source_index"), dict):
            payload["analyst_report"] = build_analyst_report(
                incident_id=incident_id,
                augmented_incident=augmented,
                source_index=payload.get("source_index", {}),
                quality_report=quality_report if isinstance(quality_report, dict) else {},
                technical_analysis=payload.get("technical_analysis") if isinstance(payload.get("technical_analysis"), dict) else None,
            )
        return payload

    def get_analyst_report(self, incident_id: str) -> dict | None:
        bundle = self.get_incident_bundle(incident_id)
        if not bundle:
            return None
        analyst_report = bundle.get("analyst_report")
        if isinstance(analyst_report, dict):
            return analyst_report
        augmented = bundle.get("augmented_incident", {})
        source_index = bundle.get("source_index", {})
        quality = bundle.get("quality_report", {})
        if not isinstance(augmented, dict) or not isinstance(source_index, dict):
            return None
        return build_analyst_report(
            incident_id=incident_id,
            augmented_incident=augmented,
            source_index=source_index,
            quality_report=quality if isinstance(quality, dict) else {},
            technical_analysis=bundle.get("technical_analysis") if isinstance(bundle.get("technical_analysis"), dict) else None,
        )

    def list_discovery_leads(self, limit: int = 40) -> list[dict]:
        now = time.time()
        if self._discovery_leads_cache and now - self._discovery_leads_cached_at < 15 * 60:
            return self._discovery_leads_cache[:limit]

        try:
            seeds = self._load_discovery_seeds_from_disk()
            leads = [self._build_incident_entry_from_seed(seed) for seed in seeds] if seeds else []
            self._discovery_leads_cache = leads
            self._discovery_leads_cached_at = now
        except Exception as exc:  # noqa: BLE001
            logger.warning("discovery.leads_failed", extra={"error": str(exc)})
            if not self._discovery_leads_cache:
                return []

        return self._discovery_leads_cache[:limit]

    def list_historical_source_leads(self, limit: int = 80) -> list[dict]:
        seeds = self._load_historical_source_seeds()
        return [self._build_incident_entry_from_seed(seed) for seed in seeds[:limit]]

    def get_discovery_overview(self) -> dict:
        default_sources = ["slowmist", "web3sec", "external_explorer", "defihacklabs"]
        schedules = self.list_schedules()
        discovery_schedule = next(
            (
                item
                for item in schedules
                if item.get("schedule_name") == "daily_discovery" or item.get("job_type") == "discovery"
            ),
            None,
        )

        latest_summary = self._read_latest_discovery_summary()
        origin_breakdown = self._build_incident_origin_breakdown()
        monitored_sources = (
            discovery_schedule.get("payload", {}).get("sources")
            if isinstance(discovery_schedule, dict)
            else None
        ) or default_sources
        execute_augmentation = (
            discovery_schedule.get("payload", {}).get("execute_augmentation")
            if isinstance(discovery_schedule, dict)
            else True
        )

        demo_count = origin_breakdown.get("demo_corpus", 0)
        auto_count = origin_breakdown.get("discovery_sync", 0)
        historical_count = len(self._load_historical_source_seeds())
        manual_count = sum(
            count
            for origin, count in origin_breakdown.items()
            if origin not in {"demo_corpus", "discovery_sync", "unknown"}
        )
        total_visible = sum(origin_breakdown.values()) + historical_count

        gap_status = "auto_primary"
        gap_summary = "Automatic discovery is now the intended front door for the product."
        if total_visible == 0:
            gap_status = "empty"
            gap_summary = "No publishable incidents are available yet, so the automatic path still needs a live feed."
        elif auto_count == 0 and demo_count > 0 and historical_count == 0:
            gap_status = "demo_heavy"
            gap_summary = "The public library is still mostly showing curated demo cases rather than auto-discovered incidents."
        elif historical_count > 0 and auto_count == 0:
            gap_status = "historical_snapshot"
            gap_summary = "The library already includes real historical incidents from source snapshots, but fresh live discovery still needs to become the default publishing path."
        elif auto_count > 0 and demo_count > auto_count:
            gap_status = "mixed"
            gap_summary = "Automatic discovery is active, but curated demo cases still make up a large part of the public library."
        elif not discovery_schedule:
            gap_status = "not_configured"
            gap_summary = "The backend can run automatic discovery, but no live discovery schedule is configured right now."

        return {
            "intended_flow": [
                "automatic discovery",
                "evidence expansion",
                "chain analysis",
                "analyst report",
            ],
            "monitored_sources": monitored_sources,
            "schedule": {
                "configured": bool(discovery_schedule),
                "status": discovery_schedule.get("status", "not_configured") if isinstance(discovery_schedule, dict) else "not_configured",
                "interval_seconds": discovery_schedule.get("interval_seconds", 0) if isinstance(discovery_schedule, dict) else 0,
                "execute_augmentation": bool(execute_augmentation),
                "last_enqueued_at": discovery_schedule.get("last_enqueued_at") if isinstance(discovery_schedule, dict) else None,
            },
            "latest_discovery_run": latest_summary,
            "incident_origin_breakdown": origin_breakdown,
            "current_gap": {
                "status": gap_status,
                "summary": gap_summary,
                "details": [
                    f"{auto_count} publishable incidents currently look auto-discovered.",
                    f"{demo_count} publishable incidents currently still come from the curated demo corpus.",
                    f"{historical_count} historical incidents currently come from stored source snapshots.",
                    f"{manual_count} publishable incidents currently come from manual or other triggers.",
                ],
            },
        }

    def _is_publishable_incident(self, *, incident_id: str, title: str) -> bool:
        haystack = f"{incident_id} {title}".lower()
        return not any(marker in haystack for marker in SYNTHETIC_INCIDENT_MARKERS)

    def _build_incident_entry_from_seed(self, seed: dict) -> dict:
        summary = (
            (seed.get("summary_candidates") or [""])[0]
            or (seed.get("note_candidates") or [""])[0]
            or "Automatically collected incident lead. Open it to inspect the source trail."
        )
        pattern_label = ""
        attack_type_raws = seed.get("attack_type_raws") or []
        if attack_type_raws:
            pattern_label = str(attack_type_raws[0]).lower().replace(" ", "_").replace("-", "_")
        source_count = len(seed.get("seed_urls") or [])
        return {
            "incident_id": seed.get("incident_id", ""),
            "title": seed.get("incident_name") or seed.get("protocol_name") or "Unnamed incident",
            "protocol_name": seed.get("protocol_name") or seed.get("incident_name") or "",
            "chain": seed.get("chain") or "unknown",
            "incident_date": seed.get("incident_date") or seed.get("date_range", {}).get("first_seen", ""),
            "summary": summary,
            "status": "auto_collected_lead",
            "completeness_score": 0.24,
            "source_count": source_count,
            "direct_source_count": source_count,
            "secondary_source_count": 0,
            "social_count": 0,
            "poc_count": 0,
            "explorer_count": len(seed.get("attack_tx_hashes") or []),
            "report_count": source_count,
            "missing_fields": ["full_augmentation", "fund_flow", "evidence_chain"],
            "last_updated": seed.get("date_range", {}).get("last_seen", "") or seed.get("incident_date", ""),
            "pattern_label": pattern_label or "price_manipulation",
            "attack_tx_hashes": seed.get("attack_tx_hashes") or [],
            "source_preview": (seed.get("seed_urls") or [])[:6],
            "origin_type": seed.get("trigger_type", "discovery_sync"),
        }

    def _build_bundle_from_discovery_lead(self, incident_id: str) -> dict | None:
        seed = self._read_discovery_seed(incident_id)
        if not seed:
            lead_entry = next((item for item in self.list_discovery_leads(limit=200) if item.get("incident_id") == incident_id), None)
            if not lead_entry:
                lead_entry = next(
                    (item for item in self.list_historical_source_leads(limit=200) if item.get("incident_id") == incident_id),
                    None,
                )
            if not lead_entry:
                return None
            seed = {
                "incident_id": lead_entry["incident_id"],
                "incident_name": lead_entry["title"],
                "protocol_name": lead_entry["protocol_name"],
                "chain": lead_entry["chain"],
                "incident_date": lead_entry["incident_date"],
                "attack_tx_hashes": lead_entry.get("attack_tx_hashes", []),
                "seed_urls": lead_entry.get("source_preview", []),
                "summary_candidates": [lead_entry.get("summary", "")],
                "attack_type_raws": [lead_entry.get("pattern_label", "price_manipulation")],
                "source_preview": lead_entry.get("source_preview", []),
                "source_count": lead_entry.get("source_count", 0),
                "direct_source_count": lead_entry.get("direct_source_count", 0),
                "last_updated": lead_entry.get("last_updated", ""),
                "pattern_label": lead_entry.get("pattern_label", "price_manipulation"),
                "trigger_type": lead_entry.get("origin_type", "discovery_sync"),
            }

        entry = self._build_incident_entry_from_seed(seed)
        title = seed.get("title") or seed.get("incident_name") or seed.get("protocol_name") or incident_id
        protocol_name = seed.get("protocol_name") or seed.get("incident_name") or title
        pattern_label = seed.get("pattern_label")
        if not pattern_label:
            attack_type_raws = seed.get("attack_type_raws") or []
            if attack_type_raws:
                pattern_label = str(attack_type_raws[0]).lower().replace(" ", "_").replace("-", "_")
        pattern_label = pattern_label or "price_manipulation"
        source_urls = seed.get("source_preview") or []
        if not source_urls:
            source_urls = seed.get("seed_urls") or []
        source_index = {
            "sources": [
                {
                    "source_id": f"src-{index + 1:03d}",
                    "url": url,
                    "source_type": "report",
                    "depth": 0,
                    "discovered_from": "discovery_sync",
                    "fetch_status": "not_fetched",
                }
                for index, url in enumerate(source_urls)
            ]
        }
        augmented_incident = {
            "incident_id": seed["incident_id"],
            "title": title,
            "incident_date": seed.get("incident_date", ""),
            "chain": seed.get("chain", "unknown"),
            "protocol_name": protocol_name,
            "status": "auto_collected_lead",
            "summary": seed.get("summary", ""),
            "key_transactions": seed.get("attack_tx_hashes", []),
            "key_addresses": [],
            "key_contracts": [],
            "timeline": [
                {
                    "label": "Incident collected from historical attack sources",
                    "summary": "This case was pulled into the library by the automatic discovery layer.",
                },
                {
                    "label": "Ready for deeper augmentation",
                    "summary": "The system already has source links and basic summaries, but the full analyst pass has not been generated yet.",
                },
            ],
            "attacker_profile": {
                "recent_activity_summary": "Only early source-level evidence is available so far. A fuller attacker profile needs the deeper augmentation pass."
            },
            "pattern_hypotheses": [{"label": pattern_label}],
            "source_summary": {
                "source_count": max(seed.get("source_count", 0), len(source_urls)),
                "direct_source_count": max(seed.get("direct_source_count", 0), len(source_urls)),
                "secondary_source_count": 0,
            },
            "quality_report": {
                "completeness_score": 0.24,
                "missing_fields": ["full_augmentation", "fund_flow", "evidence_chain"],
            },
        }
        quality_report = {
            "completeness_score": 0.24,
            "direct_source_count": seed.get("direct_source_count", 0),
            "secondary_source_count": 0,
            "fetched_source_count": 0,
            "citation_coverage_count": 0,
            "missing_fields": ["full_augmentation", "fund_flow", "evidence_chain"],
            "judge_summary": "This incident is already in the automatic collection layer, but the deeper analyst report still needs a full augmentation pass.",
        }
        analyst_report = build_analyst_report(
            incident_id=incident_id,
            augmented_incident=augmented_incident,
            source_index=source_index,
            quality_report=quality_report,
        )
        return {
            "incident_id": incident_id,
            "incident_library_entry": entry,
            "augmented_incident": augmented_incident,
            "source_index": source_index,
            "source_documents": {"documents": []},
            "quality_report": quality_report,
            "run_state": {
                "current_stage": "auto_collected_lead",
                "node_status": {},
                "updated_at": seed.get("last_updated", "") or seed.get("incident_date", ""),
            },
            "run_events": {
                "events": [
                    {
                        "stage": "discovery_sync",
                        "agent": "Discovery collectors",
                        "status": "completed",
                        "note": "This incident is visible because the automatic collectors already found it in historical source coverage.",
                    }
                ]
            },
            "agent_trace": {
                "agents": [
                    {
                        "agent_name": "Discovery collectors",
                        "status": "completed",
                        "note": "Historical incident lead captured automatically.",
                    }
                ]
            },
            "analyst_report": analyst_report,
        }

    def _read_discovery_seed(self, incident_id: str) -> dict | None:
        path = settings.runs_dir / "discovery_seeds" / f"{incident_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _historical_source_cache_path(self) -> Path:
        return settings.runs_dir / "_history_cache" / HISTORY_CACHE_NAME

    def _load_historical_source_seeds(self) -> list[dict]:
        cache_path = self._historical_source_cache_path()
        if cache_path.exists():
            cached = read_history_cache(cache_path)
            if cached:
                return cached
        seeds = build_primary_source_history_index(repo_root=REPO_ROOT)
        if seeds:
            write_history_cache(cache_path, seeds)
        return seeds

    def _load_discovery_seeds_from_disk(self) -> list[dict]:
        seeds_dir = settings.runs_dir / "discovery_seeds"
        if not seeds_dir.exists():
            return []
        seeds = [json.loads(path.read_text()) for path in seeds_dir.glob("*.json")]
        seeds.sort(
            key=lambda item: (
                item.get("incident_date", ""),
                item.get("date_range", {}).get("last_seen", ""),
            ),
            reverse=True,
        )
        return seeds

    def _read_latest_discovery_summary(self) -> dict | None:
        summary_dir = settings.runs_dir / "_discovery_jobs"
        if not summary_dir.exists():
            return None
        candidates = sorted(summary_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        latest_path = candidates[0]
        payload = json.loads(latest_path.read_text())
        payload["job_id"] = latest_path.stem
        payload["completed_at"] = datetime.fromtimestamp(
            latest_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        return payload

    def _build_incident_origin_breakdown(self) -> dict[str, int]:
        if not settings.runs_dir.exists():
            return {}
        breakdown: dict[str, int] = {}
        for run_dir in settings.runs_dir.iterdir():
            if not run_dir.is_dir() or run_dir.name.startswith("_"):
                continue
            title = ""
            incident_id = run_dir.name
            entry_path = run_dir / "incident_library_entry.json"
            if entry_path.exists():
                entry = json.loads(entry_path.read_text())
                incident_id = entry.get("incident_id", incident_id)
                title = entry.get("title", "")
            if not self._is_publishable_incident(incident_id=incident_id, title=title):
                continue

            origin = "unknown"
            run_state_path = run_dir / "run_state.json"
            if run_state_path.exists():
                run_state = json.loads(run_state_path.read_text())
                origin = run_state.get("trigger_type") or origin
            breakdown[origin] = breakdown.get(origin, 0) + 1
        return dict(sorted(breakdown.items(), key=lambda item: (-item[1], item[0])))

    def list_schedules(self) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT schedule_name, job_type, status, interval_seconds, payload_json, last_enqueued_at
                FROM schedules
                ORDER BY schedule_name ASC
                """
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            items.append(item)
        return items

    def _mark_job(self, job_id: str, status: str, result_run_dir: str | None = None, error_message: str | None = None) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, result_run_dir = COALESCE(?, result_run_dir), error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, result_run_dir, error_message, utc_now_iso(), job_id),
            )

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item.job_type == "augment" and item.seed_path:
                # Compute run_dir from seed now so progress endpoint can read run_state.json mid-run
                seed = load_seed(item.seed_path)
                run_dir = settings.runs_dir / seed.incident_id
                self._mark_job(item.job_id, "running", result_run_dir=str(run_dir))
                logger.info("job.started", extra={"job_id": item.job_id, "job_type": "augment", "run_dir": str(run_dir)})
                start_ts = time.perf_counter()
                try:
                    run_dir = run_augmentation_mvp(seed_path=item.seed_path, runs_dir=settings.runs_dir)
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "completed", result_run_dir=str(run_dir))
                    logger.info(
                        "job.completed",
                        extra={"job_id": item.job_id, "job_type": "augment", "duration_ms": duration_ms},
                    )
                except Exception as exc:  # noqa: BLE001
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "failed", error_message=str(exc))
                    logger.error(
                        "job.failed",
                        extra={"job_id": item.job_id, "job_type": "augment",
                               "duration_ms": duration_ms, "error": str(exc)},
                        exc_info=True,
                    )
            elif item.job_type == "discovery":
                self._mark_job(item.job_id, "running")
                self.write_job_progress(
                    item.job_id,
                    status="running",
                    current_stage="discovery_sync",
                    stages=[{"name": "discovery_sync", "status": "running"}],
                    detail="Scanning configured sources and preparing follow-up incident seeds.",
                )
                logger.info("job.started", extra={"job_id": item.job_id, "job_type": "discovery"})
                start_ts = time.perf_counter()
                try:
                    payload = item.payload or {}
                    summary = run_discovery_sync(
                        sources=payload.get("sources", ["slowmist", "web3sec", "external_explorer", "defihacklabs"]),
                        seeds_dir=payload.get("seeds_dir", settings.runs_dir / "discovery_seeds"),
                        runs_dir=payload.get("runs_dir", settings.runs_dir),
                        execute_augmentation=payload.get("execute_augmentation", True),
                    )
                    summary_dir = settings.runs_dir / "_discovery_jobs"
                    summary_dir.mkdir(parents=True, exist_ok=True)
                    summary_path = summary_dir / f"{item.job_id}.json"
                    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "completed", result_run_dir=str(summary_path))
                    self.write_job_progress(
                        item.job_id,
                        status="completed",
                        current_stage="completed",
                        stages=[{"name": "discovery_sync", "status": "completed"}],
                        detail="Discovery finished and the summary file was written.",
                    )
                    logger.info(
                        "job.completed",
                        extra={"job_id": item.job_id, "job_type": "discovery", "duration_ms": duration_ms},
                    )
                except Exception as exc:  # noqa: BLE001
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "failed", error_message=str(exc))
                    self.write_job_progress(
                        item.job_id,
                        status="failed",
                        current_stage="failed",
                        stages=[{"name": "discovery_sync", "status": "failed"}],
                        detail=str(exc),
                    )
                    logger.error(
                        "job.failed",
                        extra={"job_id": item.job_id, "job_type": "discovery",
                               "duration_ms": duration_ms, "error": str(exc)},
                        exc_info=True,
                    )
            elif item.job_type == "demo_corpus":
                self._mark_job(item.job_id, "running")
                self.write_job_progress(
                    item.job_id,
                    status="running",
                    current_stage="build_demo_corpus",
                    stages=[{"name": "build_demo_corpus", "status": "running"}],
                    detail="Rebuilding the public demo incident set from the configured source pack.",
                )
                logger.info("job.started", extra={"job_id": item.job_id, "job_type": "demo_corpus"})
                start_ts = time.perf_counter()
                try:
                    summary = build_demo_corpus(
                        sample_targets_path=settings.sample_targets_path,
                        runs_dir=settings.runs_dir,
                    )
                    summary_dir = settings.runs_dir / "_demo_seed_inputs"
                    summary_dir.mkdir(parents=True, exist_ok=True)
                    summary_path = summary_dir / "demo_corpus_summary.json"
                    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "completed", result_run_dir=str(summary_path))
                    self.write_job_progress(
                        item.job_id,
                        status="completed",
                        current_stage="completed",
                        stages=[{"name": "build_demo_corpus", "status": "completed"}],
                        detail="Demo corpus rebuild finished and the summary file was written.",
                    )
                    logger.info(
                        "job.completed",
                        extra={"job_id": item.job_id, "job_type": "demo_corpus", "duration_ms": duration_ms},
                    )
                except Exception as exc:  # noqa: BLE001
                    duration_ms = round((time.perf_counter() - start_ts) * 1000)
                    self._mark_job(item.job_id, "failed", error_message=str(exc))
                    self.write_job_progress(
                        item.job_id,
                        status="failed",
                        current_stage="failed",
                        stages=[{"name": "build_demo_corpus", "status": "failed"}],
                        detail=str(exc),
                    )
                    logger.error(
                        "job.failed",
                        extra={"job_id": item.job_id, "job_type": "demo_corpus",
                               "duration_ms": duration_ms, "error": str(exc)},
                        exc_info=True,
                    )

            self.queue.task_done()

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            with get_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT schedule_name, interval_seconds, payload_json, last_enqueued_at
                    FROM schedules
                    WHERE status = 'active'
                    """
                ).fetchall()

                now_ts = time.time()
                for row in rows:
                    last = row["last_enqueued_at"]
                    last_ts = 0.0
                    if last:
                        try:
                            last_ts = float(last)
                        except ValueError:
                            last_ts = 0.0

                    if now_ts - last_ts < row["interval_seconds"]:
                        continue

                    job_id = f"job-{uuid4().hex[:12]}"
                    created_at = utc_now_iso()
                    connection.execute(
                        """
                        INSERT INTO jobs (job_id, incident_id, job_type, status, seed_path, result_run_dir, error_message, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (job_id, None, "discovery", "queued", None, None, None, created_at, created_at),
                    )
                    connection.execute(
                        """
                        UPDATE schedules
                        SET last_enqueued_at = ?
                        WHERE schedule_name = ?
                        """,
                        (str(now_ts), row["schedule_name"]),
                    )
                    self.queue.put(
                        QueuedJob(
                            job_id=job_id,
                            job_type="discovery",
                            payload=json.loads(row["payload_json"]),
                        )
                    )

            time.sleep(1.0)


job_manager = JobManager()

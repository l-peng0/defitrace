from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import settings


def ensure_database() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL UNIQUE,
                incident_id TEXT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                seed_path TEXT,
                result_run_dir TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_name TEXT NOT NULL UNIQUE,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                interval_seconds INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                last_enqueued_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_token TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def upsert_schedule(
    schedule_name: str,
    job_type: str,
    status: str,
    interval_seconds: int,
    payload: dict,
) -> None:
    payload_json = json.dumps(payload, ensure_ascii=True)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO schedules (schedule_name, job_type, status, interval_seconds, payload_json, last_enqueued_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            ON CONFLICT(schedule_name) DO UPDATE SET
                job_type=excluded.job_type,
                status=excluded.status,
                interval_seconds=excluded.interval_seconds,
                payload_json=excluded.payload_json
            """,
            (schedule_name, job_type, status, interval_seconds, payload_json),
        )

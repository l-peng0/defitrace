from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .config import settings
from .database import get_connection


PBKDF2_ITERATIONS = 200_000
WRITE_ROLES = {"operator", "admin"}


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def user_response(row: dict) -> dict:
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def count_users() -> int:
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    return int(row["count"])


def create_user(email: str, password: str) -> dict:
    normalized_email = normalize_email(email)
    role = "admin" if count_users() == 0 else "viewer"
    now = utc_now_iso()
    user_id = f"user_{secrets.token_hex(8)}"

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (user_id, email, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            """,
            (user_id, normalized_email, hash_password(password), role, now, now),
        )
        row = connection.execute(
            """
            SELECT user_id, email, role, status, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return user_response(dict(row))


def get_user_by_email(email: str) -> dict | None:
    normalized_email = normalize_email(email)
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id, email, password_hash, role, status, created_at, updated_at
            FROM users
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id, email, role, status, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return user_response(dict(row)) if row else None


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (session_token, user_id, created_at, expires_at, last_used_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, user_id, now.isoformat(), expires_at.isoformat(), now.isoformat()),
        )
    return token


def get_session_user(session_token: str) -> dict | None:
    now = utc_now_iso()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT users.user_id, users.email, users.role, users.status, users.created_at, users.updated_at
            FROM sessions
            JOIN users ON users.user_id = sessions.user_id
            WHERE sessions.session_token = ?
              AND sessions.expires_at > ?
              AND users.status = 'active'
            """,
            (session_token, now),
        ).fetchone()
        if row:
            connection.execute(
                """
                UPDATE sessions
                SET last_used_at = ?
                WHERE session_token = ?
                """,
                (now, session_token),
            )
    return user_response(dict(row)) if row else None


def delete_session(session_token: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))


def list_users() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_id, email, role, status, created_at, updated_at
            FROM users
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [user_response(dict(row)) for row in rows]


def update_user_role(user_id: str, role: str) -> dict | None:
    now = utc_now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET role = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (role, now, user_id),
        )
        row = connection.execute(
            """
            SELECT user_id, email, role, status, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return user_response(dict(row)) if row else None


@dataclass
class AuthResult:
    user: dict
    token: str

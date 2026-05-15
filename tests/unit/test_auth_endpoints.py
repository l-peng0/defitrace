"""Tests for session auth and role-gated write access."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def make_client(tmp_db: Path) -> TestClient:
    from backend.app import app, job_manager

    stack = ExitStack()
    db_settings = stack.enter_context(patch("backend.database.settings"))
    auth_settings = stack.enter_context(patch("backend.auth.settings"))
    app_settings = stack.enter_context(patch("backend.app.settings"))
    stack.enter_context(patch.object(job_manager, "start"))
    stack.enter_context(patch.object(job_manager, "stop"))
    stack.enter_context(patch.object(job_manager, "list_jobs", return_value=[]))

    db_settings.database_path = tmp_db
    auth_settings.session_ttl_seconds = 3600
    app_settings.api_token = ""
    app_settings.cors_allow_origins = []

    client = TestClient(app, raise_server_exceptions=False)
    client._test_stack = stack  # type: ignore[attr-defined]
    return client


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestAuthEndpoints:
    def test_first_registered_user_becomes_admin(self, tmp_db: Path) -> None:
        client = make_client(tmp_db)
        try:
            response = client.post(
                "/api/auth/register",
                json={"email": "admin@example.com", "password": "strong-pass-1"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["user"]["email"] == "admin@example.com"
            assert body["user"]["role"] == "admin"

            me = client.get("/api/auth/me", headers=auth_headers(body["token"]))
            assert me.status_code == 200
            assert me.json()["role"] == "admin"
        finally:
            client._test_stack.close()  # type: ignore[attr-defined]

    def test_viewer_cannot_use_write_endpoints_until_promoted(self, tmp_db: Path) -> None:
        client = make_client(tmp_db)
        try:
            admin = client.post(
                "/api/auth/register",
                json={"email": "admin@example.com", "password": "strong-pass-1"},
            ).json()
            viewer = client.post(
                "/api/auth/register",
                json={"email": "viewer@example.com", "password": "strong-pass-2"},
            ).json()

            denied = client.get("/api/jobs", headers=auth_headers(viewer["token"]))
            assert denied.status_code == 403

            promoted = client.post(
                f"/api/auth/users/{viewer['user']['user_id']}/role",
                headers=auth_headers(admin["token"]),
                json={"role": "operator"},
            )
            assert promoted.status_code == 200
            assert promoted.json()["role"] == "operator"

            allowed = client.get("/api/jobs", headers=auth_headers(viewer["token"]))
            assert allowed.status_code == 200
            assert allowed.json() == []
        finally:
            client._test_stack.close()  # type: ignore[attr-defined]

    def test_augmentation_requires_real_signal(self, tmp_db: Path) -> None:
        client = make_client(tmp_db)
        try:
            admin = client.post(
                "/api/auth/register",
                json={"email": "admin@example.com", "password": "strong-pass-1"},
            ).json()

            response = client.post(
                "/api/jobs/augment",
                headers=auth_headers(admin["token"]),
                json={"chain": "Ethereum"},
            )
            assert response.status_code == 422
        finally:
            client._test_stack.close()  # type: ignore[attr-defined]

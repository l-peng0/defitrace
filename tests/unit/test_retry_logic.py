"""Tests for tenacity retry logic in source_expansion.fetch_source_document."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import requests
import pytest


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tenacity retries instant so tests don't wait."""
    monkeypatch.setattr("time.sleep", lambda _: None)


class TestFetchSourceDocumentRetry:
    """fetch_source_document must retry on transient network errors (up to 3 attempts)."""

    def test_succeeds_on_first_attempt_when_no_error(self) -> None:
        from incident_augmentation.source_expansion import fetch_source_document

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.content = b"<html><body>Hello</body></html>"

        with patch("incident_augmentation.source_expansion.requests.get", return_value=mock_response) as mock_get:
            doc = fetch_source_document("src-001", "https://example.com", "report")

        assert doc.fetch_status == "fetched"
        assert mock_get.call_count == 1

    def test_retries_on_connection_error_and_succeeds(self) -> None:
        from incident_augmentation.source_expansion import fetch_source_document

        good_response = MagicMock()
        good_response.status_code = 200
        good_response.headers = {"Content-Type": "text/html"}
        good_response.content = b"<html><body>Hello</body></html>"

        with patch(
            "incident_augmentation.source_expansion.requests.get",
            side_effect=[
                requests.ConnectionError("refused"),
                good_response,
            ],
        ) as mock_get:
            doc = fetch_source_document("src-001", "https://example.com", "report")

        assert doc.fetch_status == "fetched", f"Expected fetched after retry, got {doc.fetch_status}"
        assert mock_get.call_count == 2

    def test_returns_network_error_after_all_retries_exhausted(self) -> None:
        from incident_augmentation.source_expansion import fetch_source_document

        with patch(
            "incident_augmentation.source_expansion.requests.get",
            side_effect=requests.ConnectionError("always fails"),
        ) as mock_get:
            doc = fetch_source_document("src-001", "https://example.com", "report")

        assert doc.fetch_status == "network_error"
        # Must have retried — at least 2 attempts, at most 3
        assert mock_get.call_count >= 2, f"Expected retries, got {mock_get.call_count} attempts"

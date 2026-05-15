"""Tests for the iterator-exhausted bug in run_discovery_sync."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock


class TestDiscoverySourceCount:
    """run_discovery_sync must report the correct source_count, not always 0.

    Bug: sources is typed as Iterable[str]. collect_records() consumes the iterator,
    then len(list(sources)) re-iterates it — getting 0.
    """

    def test_source_count_is_non_zero_for_named_sources(self, tmp_path: Path) -> None:
        from incident_augmentation.discovery import run_discovery_sync

        # Use a generator — the bug: iterator is consumed by collect_records,
        # then len(list(sources)) returns 0 because the generator is exhausted.
        def source_gen():
            yield "slowmist"
            yield "external_explorer"

        def consuming_collect_records(sources, **kwargs):
            list(sources)  # consume the iterator, as the real collect_records does
            return []

        with patch("incident_augmentation.discovery.collect_records", side_effect=consuming_collect_records), \
             patch("incident_augmentation.discovery.group_records_to_incidents", return_value=[]), \
             patch("incident_augmentation.discovery.write_seed_payloads", return_value=[]):

            result = run_discovery_sync(
                sources=source_gen(),
                seeds_dir=tmp_path,
                runs_dir=tmp_path,
                execute_augmentation=False,
            )

        # source_count must be 2, not 0 (the iterator-exhausted bug)
        assert result["source_count"] == 2, (
            f"Expected source_count=2, got {result['source_count']} (iterator exhausted bug)"
        )

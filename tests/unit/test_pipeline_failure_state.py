"""Tests for pipeline failure state — run_state.json must show 'failed' on crash."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


class TestPipelineFailureState:
    """When run_augmentation_mvp raises mid-run, run_state.json must be updated
    with status='failed' so the progress endpoint does not show stale in-progress state.
    """

    def test_run_state_written_as_failed_on_pipeline_exception(self, tmp_path: Path) -> None:
        seed_content = {
            "incident_id": "test-inc",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        # Patch expand_sources to raise so the pipeline crashes mid-run
        from incident_augmentation.pipeline import run_augmentation_mvp
        with patch(
            "incident_augmentation.pipeline.expand_sources",
            side_effect=RuntimeError("network timeout"),
        ):
            try:
                run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)
            except RuntimeError:
                pass  # expected

        run_dir = tmp_path / "manual-eth"
        run_state_path = run_dir / "run_state.json"
        assert run_state_path.exists(), "run_state.json must exist even after crash"

        run_state = json.loads(run_state_path.read_text())
        assert run_state.get("current_stage") == "failed", (
            f"Expected current_stage='failed', got {run_state.get('current_stage')!r}"
        )
        assert "network timeout" in run_state.get("run_notes", [])[-1], (
            "Error message must appear in run_notes"
        )

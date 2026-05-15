"""Unit + integration tests for incident_augmentation.agent_trace."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from incident_augmentation.agent_trace import (
    AgentTraceRecord,
    TraceCollector,
    _NullTraceCollector,
    null_trace,
)


# ---------------------------------------------------------------------------
# Unit tests: TraceCollector.record()
# ---------------------------------------------------------------------------


class TestTraceCollectorRecord:
    def test_record_appends_one_entry(self) -> None:
        tc = TraceCollector()
        with tc.record("collector", agent_type="rule", input_summary="tx 0xabc") as slot:
            slot.output_summary = "3 bundles collected"
        assert len(tc.records) == 1
        rec = tc.records[0]
        assert rec.agent_name == "collector"
        assert rec.agent_type == "rule"
        assert rec.output_summary == "3 bundles collected"

    def test_record_duration_is_positive(self) -> None:
        tc = TraceCollector()
        with tc.record("planner") as _slot:
            import time
            time.sleep(0.001)
        assert tc.records[0].duration_ms >= 0  # may be 0 on fast CI

    def test_record_started_at_is_iso8601_utc(self) -> None:
        import re
        tc = TraceCollector()
        with tc.record("collector"):
            pass
        started = tc.records[0].started_at
        # Should match ISO 8601 with Z suffix, e.g. 2026-04-27T12:34:56.789Z
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", started), (
            f"started_at not in expected ISO 8601 format: {started}"
        )

    def test_to_dict_has_all_required_schema_keys(self) -> None:
        tc = TraceCollector()
        with tc.record("collector", agent_type="rule"):
            pass

        expected_record_keys = {
            "agent_name",
            "agent_type",
            "started_at",
            "duration_ms",
            "input_summary",
            "output_summary",
            "llm_provider",
            "prompt_tokens",
            "completion_tokens",
            "notes",
        }
        record_dict = tc.records[0].to_dict()
        assert set(record_dict.keys()) == expected_record_keys

    def test_exception_in_block_reraises_and_marks_errored(self) -> None:
        tc = TraceCollector()
        with pytest.raises(ValueError, match="boom"):
            with tc.record("evidence_extractor", agent_type="llm") as slot:
                slot.notes = "initial note"
                raise ValueError("boom")

        # Record should still be appended
        assert len(tc.records) == 1
        rec = tc.records[0]
        assert "[errored]" in rec.notes

    def test_exception_preserves_initial_notes(self) -> None:
        tc = TraceCollector()
        with pytest.raises(RuntimeError):
            with tc.record("planner", notes="my note") as _slot:
                raise RuntimeError("oops")
        assert "my note" in tc.records[0].notes
        assert "[errored]" in tc.records[0].notes

    def test_slot_fields_are_captured(self) -> None:
        tc = TraceCollector()
        with tc.record("narrative_writer", agent_type="llm") as slot:
            slot.output_summary = "summary written"
            slot.llm_provider = "GLM"
            slot.prompt_tokens = 100
            slot.completion_tokens = 200
            slot.notes = "custom note"
        rec = tc.records[0]
        assert rec.output_summary == "summary written"
        assert rec.llm_provider == "GLM"
        assert rec.prompt_tokens == 100
        assert rec.completion_tokens == 200
        assert rec.notes == "custom note"


# ---------------------------------------------------------------------------
# Unit tests: loop flags
# ---------------------------------------------------------------------------


class TestLoopFlags:
    def test_set_revision_marks_triggered(self) -> None:
        tc = TraceCollector()
        assert tc.revision_triggered is False
        assert tc.revision_critique is None
        tc.set_revision("missing tx role map")
        assert tc.revision_triggered is True
        assert tc.revision_critique == "missing tx role map"

    def test_set_qa_retry_marks_triggered(self) -> None:
        tc = TraceCollector()
        assert tc.qa_retry_triggered is False
        tc.set_qa_retry("score too low")
        assert tc.qa_retry_triggered is True
        assert tc.qa_retry_critique == "score too low"


# ---------------------------------------------------------------------------
# Unit tests: to_dict() schema shape
# ---------------------------------------------------------------------------


class TestToDictSchema:
    def test_top_level_keys_match_frontend_schema(self) -> None:
        tc = TraceCollector()
        with tc.record("collector"):
            pass
        d = tc.to_dict()
        expected_keys = {
            "revision_triggered",
            "revision_critique",
            "qa_retry_triggered",
            "qa_retry_critique",
            "records",
        }
        assert set(d.keys()) == expected_keys

    def test_record_keys_match_frontend_schema(self) -> None:
        tc = TraceCollector()
        with tc.record("collector", agent_type="rule"):
            pass
        record_dict = tc.to_dict()["records"][0]
        expected_keys = {
            "agent_name",
            "agent_type",
            "started_at",
            "duration_ms",
            "input_summary",
            "output_summary",
            "llm_provider",
            "prompt_tokens",
            "completion_tokens",
            "notes",
        }
        assert set(record_dict.keys()) == expected_keys

    def test_initial_flags_are_false_and_none(self) -> None:
        tc = TraceCollector()
        d = tc.to_dict()
        assert d["revision_triggered"] is False
        assert d["revision_critique"] is None
        assert d["qa_retry_triggered"] is False
        assert d["qa_retry_critique"] is None
        assert d["records"] == []

    def test_multiple_records_serialise_in_order(self) -> None:
        tc = TraceCollector()
        for name in ["collector", "planner", "contract_intelligence"]:
            with tc.record(name):
                pass
        d = tc.to_dict()
        names = [r["agent_name"] for r in d["records"]]
        assert names == ["collector", "planner", "contract_intelligence"]


# ---------------------------------------------------------------------------
# Unit tests: to_markdown()
# ---------------------------------------------------------------------------


class TestToMarkdown:
    def test_to_markdown_non_empty(self) -> None:
        tc = TraceCollector()
        with tc.record("collector"):
            pass
        md = tc.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0

    def test_to_markdown_contains_all_agent_names(self) -> None:
        tc = TraceCollector()
        agents = ["collector", "planner", "evidence_extractor", "quality_assessor"]
        for agent in agents:
            with tc.record(agent):
                pass
        md = tc.to_markdown()
        for agent in agents:
            assert agent in md, f"Agent '{agent}' not found in markdown output"

    def test_to_markdown_flags_revision_when_set(self) -> None:
        tc = TraceCollector()
        tc.set_revision("needs more tx detail")
        with tc.record("collector"):
            pass
        md = tc.to_markdown()
        assert "revision" in md.lower()

    def test_to_markdown_flags_qa_retry_when_set(self) -> None:
        tc = TraceCollector()
        tc.set_qa_retry("score 0.3 too low")
        with tc.record("quality_assessor"):
            pass
        md = tc.to_markdown()
        assert "retry" in md.lower() or "qa" in md.lower()

    def test_to_markdown_shows_duration(self) -> None:
        tc = TraceCollector()
        with tc.record("planner"):
            pass
        md = tc.to_markdown()
        # Should contain "ms" from duration display
        assert "ms" in md


# ---------------------------------------------------------------------------
# Unit tests: null_trace()
# ---------------------------------------------------------------------------


class TestNullTrace:
    def test_null_trace_returns_null_collector(self) -> None:
        nt = null_trace()
        assert isinstance(nt, _NullTraceCollector)

    def test_null_trace_record_does_not_append(self) -> None:
        nt = null_trace()
        with nt.record("collector"):
            pass
        assert nt.records == []

    def test_null_trace_set_revision_is_noop(self) -> None:
        nt = null_trace()
        nt.set_revision("critique")
        assert nt.revision_triggered is False

    def test_null_trace_to_dict_returns_empty_schema(self) -> None:
        nt = null_trace()
        d = nt.to_dict()
        assert d["records"] == []
        assert d["revision_triggered"] is False
        assert d["qa_retry_triggered"] is False

    def test_null_trace_to_markdown_returns_string(self) -> None:
        nt = null_trace()
        md = nt.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0


# ---------------------------------------------------------------------------
# Integration test: pipeline end-to-end with mocked LLM stages
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def glm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLM_API_KEY", "test-key-for-trace-tests")


def _make_llm_response_for(payload: dict | list) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = json.dumps(payload)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 50
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = "glm-4-plus"
    return mock_response


class TestPipelineTraceIntegration:
    """Verify that after a full pipeline run:
    - augmented_incident.json contains pipeline_trace with the right schema
    - pipeline_trace.md is written to disk
    - record count matches expected (4 for no retry, 8 for retry pass)
    """

    def _run_pipeline(
        self,
        tmp_path: Path,
        incident_id: str,
        first_pass_score: float = 0.85,
        second_pass_score: float = 0.9,
    ) -> tuple[Path, dict]:
        seed_content = {
            "incident_id": incident_id,
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "TraceTest",
            "incident_date": "2026-04-27",
            "seed_urls": [],
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        _qa_call_count = {"n": 0}

        def fake_create(**kwargs):
            messages = kwargs.get("messages", [])
            system = next((m["content"] for m in messages if m.get("role") == "system"), "")
            if "extracting structured facts" in system:
                r = MagicMock()
                r.choices = [MagicMock()]
                r.choices[0].message.content = "[]"
                r.usage = MagicMock()
                r.usage.prompt_tokens = 10
                r.usage.completion_tokens = 10
                r.model = "glm-4-flash"
                return r
            elif "synthesizing an attack timeline" in system:
                return _make_llm_response_for({
                    "incident_id": incident_id,
                    "steps": [],
                    "synthesis_note": "ok",
                })
            elif "human-readable incident report" in system:
                return _make_llm_response_for({
                    "executive_summary": "Exploit happened.",
                    "attack_narrative": "Details.",
                    "attacker_motive": "Profit.",
                    "key_takeaway": "Patch it.",
                })
            else:
                _qa_call_count["n"] += 1
                score = first_pass_score if _qa_call_count["n"] == 1 else second_pass_score
                missing_dims = [] if score >= 0.7 else ["financial_impact"]
                return _make_llm_response_for({
                    "completeness_score": score,
                    "missing_fields": [],
                    "missing_dimensions": missing_dims,
                    "judge_summary": f"Pass {_qa_call_count['n']}.",
                    "gaps": [],
                    "recommendations": [],
                })

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch, \
             patch("incident_augmentation.pipeline.run_incident_technical_analysis", return_value={"status": "skipped"}):
            mock_fetch.side_effect = Exception("no network in tests")
            from incident_augmentation.pipeline import run_augmentation_mvp
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        augmented = json.loads((run_dir / "augmented_incident.json").read_text())
        return run_dir, augmented

    def test_pipeline_trace_field_present_in_augmented_incident(self, tmp_path: Path) -> None:
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-no-retry-2026", first_pass_score=0.85)
        assert "pipeline_trace" in augmented, "pipeline_trace must be present in augmented_incident.json"

    def test_pipeline_trace_schema_has_required_top_level_keys(self, tmp_path: Path) -> None:
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-schema-2026", first_pass_score=0.85)
        pt = augmented["pipeline_trace"]
        expected_keys = {"revision_triggered", "revision_critique", "qa_retry_triggered", "qa_retry_critique", "records"}
        assert set(pt.keys()) == expected_keys

    def test_pipeline_trace_record_schema_keys(self, tmp_path: Path) -> None:
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-record-schema-2026", first_pass_score=0.85)
        records = augmented["pipeline_trace"]["records"]
        assert len(records) > 0
        expected_keys = {
            "agent_name", "agent_type", "started_at", "duration_ms",
            "input_summary", "output_summary", "llm_provider",
            "prompt_tokens", "completion_tokens", "notes",
        }
        for rec in records:
            assert set(rec.keys()) == expected_keys, f"Record for {rec.get('agent_name')} has wrong keys"

    def test_no_retry_produces_4_llm_records(self, tmp_path: Path) -> None:
        """With score >= 0.7, no retry fires. Expect exactly 4 LLM agent records."""
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-4-records-2026", first_pass_score=0.85)
        records = augmented["pipeline_trace"]["records"]
        llm_records = [r for r in records if r["agent_type"] == "llm"]
        assert len(llm_records) == 4, (
            f"Expected 4 LLM records (evidence, timeline, narrative, quality_assessor), got {len(llm_records)}: "
            f"{[r['agent_name'] for r in llm_records]}"
        )

    def test_retry_produces_8_llm_records(self, tmp_path: Path) -> None:
        """With score < 0.7, retry fires. Expect 8 LLM records (4 + 4)."""
        _run_dir, augmented = self._run_pipeline(
            tmp_path,
            "trace-8-records-2026",
            first_pass_score=0.3,
            second_pass_score=0.9,
        )
        records = augmented["pipeline_trace"]["records"]
        llm_records = [r for r in records if r["agent_type"] == "llm"]
        assert len(llm_records) == 8, (
            f"Expected 8 LLM records (4 v1 + 4 v2), got {len(llm_records)}: "
            f"{[r['agent_name'] for r in llm_records]}"
        )

    def test_no_retry_qa_retry_triggered_false(self, tmp_path: Path) -> None:
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-no-retry-flag-2026", first_pass_score=0.85)
        assert augmented["pipeline_trace"]["qa_retry_triggered"] is False

    def test_retry_qa_retry_triggered_true(self, tmp_path: Path) -> None:
        _run_dir, augmented = self._run_pipeline(
            tmp_path, "trace-retry-flag-2026",
            first_pass_score=0.3, second_pass_score=0.9,
        )
        assert augmented["pipeline_trace"]["qa_retry_triggered"] is True
        assert augmented["pipeline_trace"]["qa_retry_critique"] is not None

    def test_pipeline_trace_md_is_written(self, tmp_path: Path) -> None:
        run_dir, _augmented = self._run_pipeline(tmp_path, "trace-md-file-2026", first_pass_score=0.85)
        md_path = run_dir / "pipeline_trace.md"
        assert md_path.exists(), "pipeline_trace.md must be written to the run directory"
        md_content = md_path.read_text(encoding="utf-8")
        assert len(md_content) > 50, "pipeline_trace.md should be non-trivial"
        # Verify known agent names appear
        assert "evidence_extractor" in md_content
        assert "timeline_synthesizer" in md_content
        assert "narrative_writer" in md_content
        assert "quality_assessor" in md_content

    def test_expected_agent_names_in_records(self, tmp_path: Path) -> None:
        """All 4 LLM stage names must appear at least once."""
        _run_dir, augmented = self._run_pipeline(tmp_path, "trace-names-2026", first_pass_score=0.85)
        names = {r["agent_name"] for r in augmented["pipeline_trace"]["records"]}
        expected = {"evidence_extractor", "timeline_synthesizer", "narrative_writer", "quality_assessor"}
        missing = expected - names
        assert not missing, f"Missing agent names in pipeline_trace.records: {missing}"

"""Integration test: pipeline with mocked LLM stages produces narrative field."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest


@pytest.fixture(autouse=True)
def glm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLM_API_KEY", "test-key-for-tests")


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


class TestPipelineLLMIntegration:
    """Full pipeline with all network calls mocked — verifies LLM stages are called
    and their output appears in the final artifacts."""

    def test_augmented_incident_contains_narrative_after_llm_run(self, tmp_path: Path) -> None:
        seed_content = {
            "incident_id": "paribus-eth-2022-10-12",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "Paribus",
            "incident_date": "2022-10-12",
            "seed_urls": [],
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        narrative_response = _make_llm_response_for({
            "executive_summary": "Paribus lost $50K via reentrancy.",
            "attack_narrative": "The attacker exploited a reentrancy bug.",
            "attacker_motive": "Financial gain.",
            "key_takeaway": "Always use reentrancy guards.",
        })
        timeline_response = _make_llm_response_for({
            "incident_id": "paribus-eth-2022-10-12",
            "steps": [{"step": 1, "timestamp": "", "actor": "attacker", "action": "Deployed exploit", "evidence_refs": [], "causal_note": ""}],
            "synthesis_note": "1 step found.",
        })
        quality_response = _make_llm_response_for({
            "completeness_score": 0.75,
            "evidence_supports_timeline": True,
            "missing_fields": [],
            "confidence_assessment": "Moderate confidence.",
            "gaps": [],
            "demo_ready": True,
            "judge_summary": "Ready for demo.",
            "recommendations": [],
        })

        def fake_create(**kwargs):
            # Route by system prompt content — avoids threading race condition on call count
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
                return timeline_response
            elif "human-readable incident report" in system:
                return narrative_response
            else:
                return quality_response

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = Exception("no network in tests")

            from incident_augmentation.pipeline import run_augmentation_mvp
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        narrative_path = run_dir / "narrative.json"
        assert narrative_path.exists(), "narrative.json must be written by narrative writer agent"
        narrative = json.loads(narrative_path.read_text())
        assert "executive_summary" in narrative

        aug = json.loads((run_dir / "augmented_incident.json").read_text())
        assert "narrative" in aug, "augmented_incident.json must have 'narrative' key"
        analyst_report = json.loads((run_dir / "analyst_report.json").read_text())
        assert analyst_report["report_type"] == "analyst_report"
        assert "case_overview" in analyst_report

    def test_pipeline_completes_even_when_all_llm_calls_fail(self, tmp_path: Path) -> None:
        """Pipeline must complete with heuristic output when all LLM calls fail."""
        from openai import APIError

        seed_content = {
            "incident_id": "fallback-eth-2022-01-01",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "TestProtocol",
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = APIError(
            message="unavailable", request=MagicMock(), body=None
        )

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = Exception("no network")

            from incident_augmentation.pipeline import run_augmentation_mvp
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        assert (run_dir / "augmented_incident.json").exists()
        assert (run_dir / "quality_report.json").exists()
        assert (run_dir / "analyst_report.json").exists()
        run_state = json.loads((run_dir / "run_state.json").read_text())
        assert run_state["current_stage"] != "failed"

    def test_pipeline_merges_technical_analysis_into_outputs(self, tmp_path: Path) -> None:
        seed_content = {
            "incident_id": "tech-merge-eth-2026-04-20",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "Tech Merge",
            "incident_date": "2026-04-20",
            "attack_tx_hashes": [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ],
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        narrative_response = _make_llm_response_for(
            {
                "executive_summary": "Tech Merge suffered a tx-driven exploit.",
                "attack_narrative": "The attacker triggered a vulnerable path.",
                "attacker_motive": "Financial gain.",
                "key_takeaway": "Harden the vulnerable path.",
            }
        )
        timeline_response = _make_llm_response_for(
            {
                "incident_id": "tech-merge-eth-2026-04-20",
                "steps": [],
                "synthesis_note": "No extra source-driven timeline steps.",
            }
        )
        quality_response = _make_llm_response_for(
            {
                "completeness_score": 0.8,
                "missing_fields": [],
                "judge_summary": "Strong enough for demo.",
            }
        )

        def fake_create(**kwargs):
            messages = kwargs.get("messages", [])
            system = next((m["content"] for m in messages if m.get("role") == "system"), "")
            if "extracting structured facts" in system:
                return _make_llm_response_for([])
            if "synthesizing an attack timeline" in system:
                return timeline_response
            if "human-readable incident report" in system:
                return narrative_response
            return quality_response

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create

        technical_payload = {
            "status": "completed",
            "primary_tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "tx_hashes": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            "transactions": [
                {
                    "tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "status": "completed",
                }
            ],
            "reasoning": {
                "exploit_mechanism": "The attack abused a vulnerable nested call path.",
            },
            "validation": {
                "verdict": "Deterministic and reasoning checks passed.",
                "unresolved_gaps": [],
            },
            "merge_back": {
                "summary": "Technical analysis confirmed the main exploit transaction.",
                "timeline_steps": [
                    {
                        "title": "Main exploit transaction",
                        "detail": "The primary tx executed the exploit path.",
                        "tx_hashes": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                    }
                ],
                "fund_flow_path": [
                    {
                        "title": "Funds leave victim contract",
                        "detail": "Value moved to the attacker-controlled receiver.",
                        "tx_hashes": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                    }
                ],
                "key_addresses": ["0x1111111111111111111111111111111111111111"],
                "key_contracts": ["0x2222222222222222222222222222222222222222"],
                "key_transactions": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                "open_questions": [],
            },
        }

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch, \
             patch("incident_augmentation.pipeline.run_incident_technical_analysis", return_value=technical_payload):
            mock_fetch.side_effect = Exception("no network in tests")

            from incident_augmentation.pipeline import run_augmentation_mvp

            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        augmented = json.loads((run_dir / "augmented_incident.json").read_text())
        assert augmented["technical_analysis"]["status"] == "completed"
        assert augmented["timeline"][0]["title"] == "Main exploit transaction"
        assert augmented["summary"] == "Technical analysis confirmed the main exploit transaction."

    def test_qa_retry_triggers_evidence_re_extraction_when_score_low(self, tmp_path: Path) -> None:
        """When QA first pass returns a low completeness_score, the pipeline must:
        - call run_llm_evidence_extractor exactly twice (v1 + retry pass)
        - pass a non-None retry_critique on the second call
        - produce a final dossier with qa_retry_triggered=True and the v2 score.
        """
        seed_content = {
            "incident_id": "qa-retry-eth-2026-01-01",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "RetryTest",
            "incident_date": "2026-01-01",
            "seed_urls": [],
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

        _qa_call_count = {"n": 0}

        def fake_create(**kwargs):
            messages = kwargs.get("messages", [])
            system = next((m["content"] for m in messages if m.get("role") == "system"), "")
            user = next((m["content"] for m in messages if m.get("role") == "user"), "")

            if "extracting structured facts" in system:
                # Evidence extractor — return empty list both times
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
                    "incident_id": "qa-retry-eth-2026-01-01",
                    "steps": [],
                    "synthesis_note": "timeline",
                })
            elif "human-readable incident report" in system:
                return _make_llm_response_for({
                    "executive_summary": "RetryTest exploit.",
                    "attack_narrative": "Details.",
                    "attacker_motive": "Profit.",
                    "key_takeaway": "Patch now.",
                })
            else:
                # Quality assessor — first call returns low score, second returns high
                _qa_call_count["n"] += 1
                if _qa_call_count["n"] == 1:
                    return _make_llm_response_for({
                        "completeness_score": 0.3,
                        "missing_fields": ["loss_amount", "attacker_address"],
                        "missing_dimensions": ["financial_impact", "attacker_identity"],
                        "judge_summary": "Too many gaps.",
                        "gaps": ["attacker identity unknown", "loss amount missing"],
                        "recommendations": ["Find attacker wallet", "Confirm USD loss"],
                    })
                else:
                    return _make_llm_response_for({
                        "completeness_score": 0.85,
                        "missing_fields": [],
                        "missing_dimensions": [],
                        "judge_summary": "Good after retry.",
                        "gaps": [],
                        "recommendations": [],
                    })

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch, \
             patch("incident_augmentation.pipeline.run_incident_technical_analysis", return_value={"status": "skipped"}), \
             patch("incident_augmentation.pipeline.run_llm_evidence_extractor", wraps=__import__("incident_augmentation.llm_stages", fromlist=["run_llm_evidence_extractor"]).run_llm_evidence_extractor) as spy_evidence:
            mock_fetch.side_effect = Exception("no network")

            from incident_augmentation.pipeline import run_augmentation_mvp
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        # Evidence extractor must have been called exactly twice
        assert spy_evidence.call_count == 2, (
            f"Expected evidence extractor called twice (v1 + retry), got {spy_evidence.call_count}"
        )
        # Second call must have retry_critique set
        _second_call_kwargs = spy_evidence.call_args_list[1][1]
        assert _second_call_kwargs.get("retry_critique") is not None, (
            "Second evidence extractor call must have retry_critique keyword argument"
        )

        augmented = json.loads((run_dir / "augmented_incident.json").read_text())
        assert augmented["qa_retry_triggered"] is True, "qa_retry_triggered must be True when retry fires"
        assert augmented["qa_retry_critique"] is not None, "qa_retry_critique must be non-None when retry fires"
        # Final dossier should reflect the v2 quality score (0.85)
        quality = json.loads((run_dir / "quality_report.json").read_text())
        assert quality["completeness_score"] >= 0.8, (
            f"Final quality score should reflect v2 result (>=0.8), got {quality['completeness_score']}"
        )
        # qa_retry subdirectory must exist with v2 artifacts
        assert (run_dir / "qa_retry" / "quality_report_v2.json").exists()

    def test_qa_retry_not_triggered_when_score_is_high(self, tmp_path: Path) -> None:
        """When QA first pass returns a high completeness_score, retry must NOT fire:
        - run_llm_evidence_extractor called exactly once
        - qa_retry_triggered must be False in the final dossier
        """
        seed_content = {
            "incident_id": "qa-no-retry-eth-2026-01-02",
            "chain": "eth",
            "seed_type": "manual",
            "trigger_type": "api",
            "protocol_name": "NoRetryTest",
            "incident_date": "2026-01-02",
            "seed_urls": [],
        }
        seed_path = tmp_path / "seed.json"
        seed_path.write_text(json.dumps(seed_content))

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
                    "incident_id": "qa-no-retry-eth-2026-01-02",
                    "steps": [],
                    "synthesis_note": "ok",
                })
            elif "human-readable incident report" in system:
                return _make_llm_response_for({
                    "executive_summary": "NoRetry exploit.",
                    "attack_narrative": "Details.",
                    "attacker_motive": "Profit.",
                    "key_takeaway": "Already good.",
                })
            else:
                # Quality assessor — first (and only) call returns high score
                return _make_llm_response_for({
                    "completeness_score": 0.9,
                    "missing_fields": [],
                    "missing_dimensions": [],
                    "judge_summary": "Excellent dossier.",
                    "gaps": [],
                    "recommendations": [],
                })

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = fake_create

        with patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client), \
             patch("incident_augmentation.source_expansion._fetch_with_retry") as mock_fetch, \
             patch("incident_augmentation.pipeline.run_incident_technical_analysis", return_value={"status": "skipped"}), \
             patch("incident_augmentation.pipeline.run_llm_evidence_extractor", wraps=__import__("incident_augmentation.llm_stages", fromlist=["run_llm_evidence_extractor"]).run_llm_evidence_extractor) as spy_evidence:
            mock_fetch.side_effect = Exception("no network")

            from incident_augmentation.pipeline import run_augmentation_mvp
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=tmp_path)

        assert spy_evidence.call_count == 1, (
            f"Evidence extractor must be called exactly once when score is high, got {spy_evidence.call_count}"
        )

        augmented = json.loads((run_dir / "augmented_incident.json").read_text())
        assert augmented["qa_retry_triggered"] is False, "qa_retry_triggered must be False when score is high"
        assert augmented["qa_retry_critique"] is None, "qa_retry_critique must be None when no retry fires"

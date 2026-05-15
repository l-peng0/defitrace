"""Tests for incident_augmentation.llm_stages — all 4 LLM agents."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def glm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure GLM_API_KEY is set so call_llm doesn't skip the model."""
    monkeypatch.setenv("GLM_API_KEY", "test-key-for-tests")


def _make_llm_response(text: str) -> MagicMock:
    """Build a fake OpenAI chat.completions response."""
    mock_message = MagicMock()
    mock_message.content = text
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = "glm-4-plus"
    return mock_response


def _patch_openai(return_value=None, side_effect=None):
    """Patch OpenAI client used inside call_llm."""
    mock_client = MagicMock()
    if side_effect:
        mock_client.chat.completions.create.side_effect = side_effect
    else:
        mock_client.chat.completions.create.return_value = return_value
    return patch("incident_augmentation.model_runtime.OpenAI", return_value=mock_client)


class TestCallLLM:
    def test_returns_response_text(self) -> None:
        from incident_augmentation.llm_stages import call_llm

        fake_response = _make_llm_response('{"result": "ok"}')
        with _patch_openai(return_value=fake_response):
            text = call_llm(
                system_prompt="You are an analyst.",
                user_prompt="Extract facts.",
                incident_id="test-inc",
                stage_name="llm_evidence_extractor",
            )

        assert text == '{"result": "ok"}'

    def test_raises_on_api_error_when_no_fallback(self) -> None:
        from incident_augmentation.llm_stages import call_llm
        from openai import APIError

        with _patch_openai(side_effect=APIError(message="rate limit", request=MagicMock(), body=None)):
            with pytest.raises(APIError):
                call_llm("sys", "user", "inc", "llm_evidence_extractor")

    def test_skips_model_when_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from incident_augmentation.llm_stages import call_llm
        from openai import APIError

        monkeypatch.setenv("GLM_API_KEY", "")
        with pytest.raises((APIError, Exception)):
            call_llm("sys", "user", "inc", "llm_evidence_extractor")


class TestLLMEvidenceExtractor:
    def test_returns_merged_evidence_with_llm_items(self) -> None:
        from incident_augmentation.llm_stages import run_llm_evidence_extractor

        llm_items = [
            {
                "fact_type": "attacker_address",
                "value": "0xabcd",
                "fact_text": "attacker used 0xabcd",
                "source_url": "https://example.com",
                "confidence": 0.92,
                "reasoning": "explicitly named in report",
            }
        ]
        fake_response = _make_llm_response(json.dumps(llm_items))
        existing_evidence = {
            "incident_id": "test-inc",
            "evidence_items": [{"evidence_id": "ev-001", "fact_type": "protocol_name", "fact_value": "TestDeFi"}],
        }
        source_documents = {"documents": [{"source_id": "src-001", "url": "https://example.com", "text_excerpt": "attacker used 0xabcd to drain funds"}]}
        seed_dict = {"incident_id": "test-inc", "protocol_name": "TestDeFi", "chain": "eth"}

        with _patch_openai(return_value=fake_response):
            result = run_llm_evidence_extractor(seed_dict, source_documents, existing_evidence, "test-inc")

        assert result["incident_id"] == "test-inc"
        all_types = [item["fact_type"] for item in result["evidence_items"]]
        assert "attacker_address" in all_types
        assert "protocol_name" in all_types

    def test_falls_back_to_heuristic_on_api_error(self) -> None:
        from incident_augmentation.llm_stages import run_llm_evidence_extractor
        from openai import APIError

        existing_evidence = {
            "incident_id": "test-inc",
            "evidence_items": [{"evidence_id": "ev-001", "fact_type": "protocol_name", "fact_value": "TestDeFi"}],
        }
        source_documents = {"documents": [{"source_id": "src-001", "url": "https://example.com", "text_excerpt": "some text"}]}
        seed_dict = {"incident_id": "test-inc", "protocol_name": "TestDeFi", "chain": "eth"}

        with _patch_openai(side_effect=APIError(message="rate limit", request=MagicMock(), body=None)):
            result = run_llm_evidence_extractor(seed_dict, source_documents, existing_evidence, "test-inc")

        assert result == existing_evidence


class TestLLMTimelineSynthesizer:
    def test_returns_llm_synthesized_timeline(self) -> None:
        from incident_augmentation.llm_stages import run_llm_timeline_synthesizer

        llm_timeline = {
            "incident_id": "test-inc",
            "steps": [{"step": 1, "timestamp": "", "actor": "attacker", "action": "Deployed flashloan contract", "evidence_refs": [], "causal_note": "Enabled price manipulation"}],
            "synthesis_note": "High confidence.",
        }
        fake_response = _make_llm_response(json.dumps(llm_timeline))
        seed_dict = {"incident_id": "test-inc", "protocol_name": "TestDeFi", "chain": "eth"}
        heuristic_timeline = {"incident_id": "test-inc", "steps": []}

        with _patch_openai(return_value=fake_response):
            result = run_llm_timeline_synthesizer(seed_dict, [], heuristic_timeline, "test-inc")

        assert result["incident_id"] == "test-inc"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["action"] == "Deployed flashloan contract"

    def test_falls_back_to_heuristic_timeline_on_api_error(self) -> None:
        from incident_augmentation.llm_stages import run_llm_timeline_synthesizer
        from openai import APIError

        heuristic_timeline = {"incident_id": "test-inc", "steps": [{"step": 1, "action": "heuristic step"}]}
        seed_dict = {"incident_id": "test-inc", "chain": "eth"}

        with _patch_openai(side_effect=APIError(message="error", request=MagicMock(), body=None)):
            result = run_llm_timeline_synthesizer(seed_dict, [], heuristic_timeline, "test-inc")

        assert result == heuristic_timeline


class TestLLMNarrativeWriter:
    def test_returns_narrative_dict(self) -> None:
        from incident_augmentation.llm_stages import run_llm_narrative_writer

        llm_narrative = {
            "executive_summary": "TestDeFi lost $1M via price manipulation.",
            "attack_narrative": "The attacker used a flashloan to manipulate the TWAP oracle...",
            "attacker_motive": "Financial gain via price manipulation.",
            "key_takeaway": "TWAP oracles need longer windows.",
        }
        fake_response = _make_llm_response(json.dumps(llm_narrative))
        seed_dict = {"incident_id": "test-inc", "protocol_name": "TestDeFi", "chain": "eth"}

        with _patch_openai(return_value=fake_response):
            result = run_llm_narrative_writer(seed_dict, [], "test-inc")

        assert "executive_summary" in result
        assert "attack_narrative" in result
        assert "attacker_motive" in result

    def test_returns_empty_narrative_on_api_error(self) -> None:
        from incident_augmentation.llm_stages import run_llm_narrative_writer
        from openai import APIError

        seed_dict = {"incident_id": "test-inc", "chain": "eth"}
        with _patch_openai(side_effect=APIError(message="error", request=MagicMock(), body=None)):
            result = run_llm_narrative_writer(seed_dict, [], "test-inc")

        assert result == {}


class TestLLMQualityAssessor:
    def test_returns_semantic_quality_report(self) -> None:
        from incident_augmentation.llm_stages import run_llm_quality_assessor

        llm_quality = {
            "completeness_score": 0.85,
            "evidence_supports_timeline": True,
            "missing_fields": [],
            "confidence_assessment": "Strong evidence from 3 sources.",
            "gaps": ["attacker identity unknown"],
            "demo_ready": True,
            "judge_summary": "Good dossier, ready for demo.",
            "recommendations": ["Add attacker wallet analysis"],
        }
        fake_response = _make_llm_response(json.dumps(llm_quality))
        seed_dict = {"incident_id": "test-inc", "protocol_name": "TestDeFi", "chain": "eth"}
        dossier_draft = {"timeline": {"steps": []}, "narrative": {}, "evidence_items": [], "source_count": 3, "heuristic_missing_fields": []}

        with _patch_openai(return_value=fake_response):
            result = run_llm_quality_assessor(seed_dict, dossier_draft, "test-inc")

        assert result["completeness_score"] == 0.85
        assert result["judge_summary"] == "Good dossier, ready for demo."

    def test_falls_back_to_heuristic_quality_on_api_error(self) -> None:
        from incident_augmentation.llm_stages import run_llm_quality_assessor
        from openai import APIError

        heuristic_quality = {"completeness_score": 0.5, "judge_summary": "heuristic", "missing_fields": []}
        seed_dict = {"incident_id": "test-inc", "chain": "eth"}
        dossier_draft = {"heuristic_quality_report": heuristic_quality}

        with _patch_openai(side_effect=APIError(message="error", request=MagicMock(), body=None)):
            result = run_llm_quality_assessor(seed_dict, dossier_draft, "test-inc")

        assert result == heuristic_quality

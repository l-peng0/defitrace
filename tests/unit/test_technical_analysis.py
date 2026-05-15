from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from incident_augmentation.models import IncidentSeed


@pytest.fixture(autouse=True)
def _disable_live_external_explorer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_EXPLORER_ACCESS_KEY", raising=False)


def _make_seed() -> IncidentSeed:
    return IncidentSeed.from_dict(
        {
            "incident_id": "tech-demo-eth-2026-04-20",
            "job_id": "job-tech-demo",
            "trigger_type": "api",
            "seed_type": "manual",
            "chain": "eth",
            "protocol_name": "Tech Demo",
            "incident_name": "Tech Demo Incident",
            "incident_date": "2026-04-20",
            "attack_tx_hashes": [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
            "seed_urls": ["https://example.com/postmortem"],
            "summary_candidates": ["A tx-driven exploit drained funds through nested calls."],
        }
    )


class TestTechnicalAnalysisService:
    def test_rpc_url_can_be_built_from_alchemy_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from incident_augmentation.tx_deep_analysis.service import _rpc_url_for_chain

        monkeypatch.delenv("CAPSTONE_RPC_ARB", raising=False)
        monkeypatch.setenv("ALCHEMY_API_KEY", "real-ish-key")

        assert _rpc_url_for_chain("Arbitrum") == "https://arb-mainnet.g.alchemy.com/v2/real-ish-key"

    def test_writes_completed_artifact_and_raw_outputs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from incident_augmentation.tx_deep_analysis.service import run_incident_technical_analysis

        seed = _make_seed()
        run_dir = tmp_path / seed.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CAPSTONE_RPC_ETH", "https://rpc.example")

        with patch(
            "incident_augmentation.tx_deep_analysis.service.collect_transaction_artifacts",
            side_effect=[
                {
                    "tx_hash": seed.attack_tx_hashes[0],
                    "status": "completed",
                    "tx_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "tx.json"),
                    "receipt_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "receipt.json"),
                    "trace_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "trace_callTracer.json"),
                    "decoded_calls_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "decoded_calls.json"),
                    "funds_flow_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "funds_flow.json"),
                    "manifest_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "manifest.json"),
                    "summary": {
                        "contracts_touched": ["0x1111111111111111111111111111111111111111"],
                        "addresses_seen": ["0x2222222222222222222222222222222222222222"],
                        "native_value_transfers": 1,
                        "token_transfers": 2,
                    },
                    "issues": [],
                },
                {
                    "tx_hash": seed.attack_tx_hashes[1],
                    "status": "partial",
                    "tx_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[1] / "tx.json"),
                    "receipt_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[1] / "receipt.json"),
                    "trace_path": "",
                    "decoded_calls_path": "",
                    "funds_flow_path": "",
                    "manifest_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[1] / "manifest.json"),
                    "summary": {
                        "contracts_touched": ["0x3333333333333333333333333333333333333333"],
                        "addresses_seen": ["0x4444444444444444444444444444444444444444"],
                        "native_value_transfers": 0,
                        "token_transfers": 0,
                    },
                    "issues": ["trace unavailable"],
                },
            ],
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.run_technical_reasoner",
            return_value={
                "attack_flow_summary": "The attacker used the first transaction to trigger the core exploit path.",
                "exploit_mechanism": "Unchecked nested call path.",
                "tx_role_map": {
                    seed.attack_tx_hashes[0]: "primary_exploit",
                    seed.attack_tx_hashes[1]: "follow_on",
                },
                "contract_role_map": {
                    "0x1111111111111111111111111111111111111111": "victim_contract",
                    "0x3333333333333333333333333333333333333333": "attacker_contract",
                },
                "timeline_steps": [
                    {
                        "title": "Primary exploit executes",
                        "detail": "The first tx drives the exploit path.",
                        "tx_hashes": [seed.attack_tx_hashes[0]],
                    }
                ],
                "funds_flow_path": [
                    {
                        "title": "Funds moved to attacker receiver",
                        "detail": "Transfers consolidate into the attacker-side address.",
                        "tx_hashes": [seed.attack_tx_hashes[0]],
                    }
                ],
                "open_questions": ["Need a fully decoded trace for the second tx."],
                "confidence_notes": ["The first tx is strongly supported by deterministic artifacts."],
            },
        ):
            result = run_incident_technical_analysis(
                seed=seed,
                run_dir=run_dir,
                source_context={"summary": "A tx-driven exploit drained funds through nested calls."},
            )

        assert result["status"] == "partial"
        artifact_path = run_dir / "technical_analysis.json"
        assert artifact_path.exists()
        payload = json.loads(artifact_path.read_text())
        assert payload["primary_tx_hash"] == seed.attack_tx_hashes[0]
        assert payload["reasoning"]["exploit_mechanism"] == "Unchecked nested call path."
        assert payload["merge_back"]["timeline_steps"][0]["title"] == "Primary exploit executes"
        assert len(payload["transactions"]) == 2

    def test_repairs_malformed_reasoning_json_and_persists_raw_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from incident_augmentation.tx_deep_analysis.service import run_incident_technical_analysis

        seed = _make_seed()
        run_dir = tmp_path / seed.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CAPSTONE_RPC_ETH", "https://rpc.example")

        with patch(
            "incident_augmentation.tx_deep_analysis.service.collect_transaction_artifacts",
            return_value={
                "tx_hash": seed.attack_tx_hashes[0],
                "status": "completed",
                "tx_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "tx.json"),
                "receipt_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "receipt.json"),
                "trace_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "trace_callTracer.json"),
                "decoded_calls_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "decoded_calls.json"),
                "funds_flow_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "funds_flow.json"),
                "manifest_path": str(run_dir / "technical_analysis" / seed.attack_tx_hashes[0] / "manifest.json"),
                "summary": {
                    "contracts_touched": ["0x1111111111111111111111111111111111111111"],
                    "addresses_seen": ["0x2222222222222222222222222222222222222222"],
                    "native_value_transfers": 1,
                    "token_transfers": 2,
                },
                "issues": [],
            },
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.call_llm_with_metadata",
            side_effect=[
                {
                    "content": '{"attack_flow_summary":"oops","exploit_mechanism":"broken',
                    "model": "glm-5",
                    "api_key_env": "GLM_API_KEY",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                },
                {
                    "content": json.dumps(
                        {
                            "attack_flow_summary": "Recovered from malformed JSON.",
                            "exploit_mechanism": "Repair path worked.",
                            "tx_role_map": {seed.attack_tx_hashes[0]: "primary_exploit"},
                            "contract_role_map": {"0x1111111111111111111111111111111111111111": "victim_contract"},
                            "timeline_steps": [],
                            "funds_flow_path": [],
                            "open_questions": [],
                            "confidence_notes": ["Repaired successfully."],
                        }
                    ),
                    "model": "glm-5-turbo",
                    "api_key_env": "GLM_API_KEY",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                },
            ],
        ):
            result = run_incident_technical_analysis(
                seed=seed,
                run_dir=run_dir,
                source_context={"summary": "A tx-driven exploit drained funds through nested calls."},
            )

        assert result["status"] == "completed"
        assert result["reasoning"]["attack_flow_summary"] == "Recovered from malformed JSON."
        raw_payload = json.loads((run_dir / "technical_reasoning_raw.json").read_text())
        repaired_payload = json.loads((run_dir / "technical_reasoning_repaired.json").read_text())
        assert raw_payload["model"] == "glm-5"
        assert repaired_payload["model"] == "glm-5-turbo"
        assert repaired_payload["repaired_payload"]["exploit_mechanism"] == "Repair path worked."

    def test_returns_skipped_when_chain_rpc_is_not_configured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from incident_augmentation.tx_deep_analysis.service import run_incident_technical_analysis

        seed = _make_seed()
        run_dir = tmp_path / seed.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.delenv("CAPSTONE_RPC_ETH", raising=False)
        monkeypatch.delenv("ALCHEMY_API_KEY", raising=False)

        result = run_incident_technical_analysis(
            seed=seed,
            run_dir=run_dir,
            source_context={"summary": "A tx-driven exploit drained funds through nested calls."},
        )

        assert result["status"] == "skipped"
        payload = json.loads((run_dir / "technical_analysis.json").read_text())
        assert "configured rpc" in payload["validation"]["verdict"].lower()

    def test_normalizes_single_string_lists_from_reasoning_payload(self) -> None:
        from incident_augmentation.tx_deep_analysis.service import _normalize_reasoning_payload

        normalized = _normalize_reasoning_payload(
            {
                "attack_flow_summary": "summary",
                "exploit_mechanism": "mechanism",
                "timeline_steps": {
                    "step": 1,
                    "description": "single object should become one-item list",
                },
                "funds_flow_path": "victim -> attacker",
                "open_questions": "how much was lost?",
                "confidence_notes": "trace supported",
            }
        )

        assert normalized["timeline_steps"] == [
            {"step": 1, "description": "single object should become one-item list"}
        ]
        assert normalized["funds_flow_path"] == [
            {"title": "Fund movement", "detail": "victim -> attacker", "tx_hashes": []}
        ]
        assert normalized["open_questions"] == ["how much was lost?"]
        assert normalized["confidence_notes"] == ["trace supported"]

    def test_generic_analyst_report_uses_technical_merge_back(self) -> None:
        from incident_augmentation.analyst_report import build_analyst_report

        report = build_analyst_report(
            incident_id="tech-demo-eth-2026-04-20",
            augmented_incident={
                "title": "Tech Demo Incident",
                "summary": "Fallback summary",
                "timeline": [
                    {
                        "title": "Primary exploit executes",
                        "detail": "The tx calls the victim contract.",
                        "timestamp": "2026-04-20T00:00:00Z",
                        "chain": "Ethereum",
                        "tx_hashes": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                        "called_contracts": ["0x1111111111111111111111111111111111111111"],
                        "function_selectors": ["0x12345678"],
                        "evidence_refs": ["technical_analysis/tx.json"],
                        "verification_status": "confirmed",
                    }
                ],
                "attacker_profile": {
                    "recent_activity_summary": "Fallback attacker summary",
                    "funding_source": "Not confirmed",
                    "post_attack_fund_flow": "Technical analysis identified 1 fund-flow step(s).",
                    "confidence": "partial",
                },
                "key_transactions": [],
                "key_addresses": [],
            },
            source_index={"sources": []},
            quality_report={"missing_fields": []},
            technical_analysis={
                "merge_back": {
                    "funds_flow_path": [
                        {
                            "title": "Funds leave victim contract",
                            "detail": "The tx-level trace shows funds moving out.",
                            "tx_hashes": [
                                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                            ],
                        }
                    ],
                    "key_transactions": [
                        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ],
                    "key_addresses": ["0x1111111111111111111111111111111111111111"],
                    "open_questions": ["Need the upstream funding path."],
                }
            },
        )

        assert report["fund_flow"]["summary"].startswith("Technical analysis")
        assert report["attacker_profile"]["funding_source"] == "Not confirmed"
        assert report["attacker_profile"]["post_attack_fund_flow"].startswith("Technical analysis")
        assert report["exploit_path"]["steps"][0]["timestamp"] == "2026-04-20T00:00:00Z"
        assert report["exploit_path"]["steps"][0]["called_contracts"] == ["0x1111111111111111111111111111111111111111"]
        assert report["exploit_path"]["steps"][0]["verification_status"] == "confirmed"
        assert report["open_questions"] == ["Need the upstream funding path."]


# ─── Stage-2 integration tests ──────────────────────────────────────────────

def _good_reasoning_for(tx_hash: str) -> dict:
    return {
        "attack_flow_summary": "Attacker drained the victim via a single swap.",
        "exploit_mechanism": "Swap pool mispricing.",
        "tx_role_map": {tx_hash: "swap_trigger"},
        "contract_role_map": {"0xvictim": "victim_contract"},
        "timeline_steps": [{"title": "Swap triggered", "detail": "", "tx_hashes": [tx_hash]}],
        "funds_flow_path": ["Funds flowed from victim pool to attacker EOA."],
        "open_questions": [],
        "confidence_notes": ["Backed by a real swap selector in trace."],
    }


def _bad_reasoning_for(tx_hash: str) -> dict:
    # Claims a flash loan trigger but the synthesized trace has only a swap.
    return {
        "attack_flow_summary": "Attacker used a flash loan to drain the pool.",
        "exploit_mechanism": "Flash-loan-driven price manipulation.",
        "tx_role_map": {tx_hash: "flash_loan_trigger"},
        "contract_role_map": {},
        "timeline_steps": [],
        "funds_flow_path": [],
        "open_questions": [],
        "confidence_notes": [],
    }


class TestStage2Integration:
    def _prepare_collector_with_real_artifacts(self, *, tx_hash: str, tx_dir: Path) -> dict:
        """Build a fake collector return dict with real JSON files on disk.

        The planner + validator stages read these files — they can't be mocked
        at the file-path level.
        """
        tx_dir.mkdir(parents=True, exist_ok=True)
        # a swap selector → planner will tag the "to" address as a router
        decoded = [
            {"path": "0", "depth": 0, "type": "CALL",
             "from": "0xeoa", "to": "0xrouter",
             "selector": "0x38ed1739", "selector_category": "swap",
             "value": 0},
        ]
        (tx_dir / "decoded_calls.json").write_text(json.dumps(decoded))
        (tx_dir / "trace_callTracer.json").write_text(json.dumps({"result": {
            "type": "CALL", "from": "0xeoa", "to": "0xrouter", "input": "0x38ed1739",
        }}))
        (tx_dir / "funds_flow.json").write_text(json.dumps({
            "native_transfers": [], "token_transfers": [],
        }))
        (tx_dir / "tx.json").write_text(json.dumps({"from": "0xeoa", "to": "0xrouter", "value": "0x0"}))
        return {
            "tx_hash": tx_hash,
            "status": "completed",
            "tx_path": str(tx_dir / "tx.json"),
            "receipt_path": "",
            "trace_path": str(tx_dir / "trace_callTracer.json"),
            "decoded_calls_path": str(tx_dir / "decoded_calls.json"),
            "funds_flow_path": str(tx_dir / "funds_flow.json"),
            "manifest_path": str(tx_dir / "manifest.json"),
            "summary": {
                "contracts_touched": ["0xrouter"],
                "addresses_seen": ["0xeoa", "0xrouter"],
                "native_value_transfers": 0,
                "token_transfers": 0,
            },
            "issues": [],
        }

    def test_full_pipeline_writes_plan_inventory_and_semantic_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from incident_augmentation.tx_deep_analysis.service import run_incident_technical_analysis

        seed = IncidentSeed.from_dict({
            "incident_id": "stage2-eth-2026",
            "job_id": "job",
            "trigger_type": "api",
            "seed_type": "manual",
            "chain": "eth",
            "protocol_name": "Stage2 Demo",
            "incident_name": "Stage2 Demo Incident",
            "incident_date": "2026-04-20",
            "attack_tx_hashes": ["0xaaa"],
            "seed_urls": [],
            "summary_candidates": ["Stage 2 integration."],
        })
        run_dir = tmp_path / seed.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CAPSTONE_RPC_ETH", "https://rpc.example")

        tx_dir = run_dir / "technical_analysis" / "0xaaa"
        collector_return = self._prepare_collector_with_real_artifacts(tx_hash="0xaaa", tx_dir=tx_dir)

        fake_inventory = {
            "incident_id": seed.incident_id,
            "chain": "eth",
            "generated_at": "now",
            "contracts": {
                "0xrouter": {
                    "address": "0xrouter", "role": "router",
                    "classification": "verified", "contract_name": "UniswapV2Router",
                    "is_proxy": False, "proxy_type": "", "implementation_address": "",
                    "compiler_version": "", "source_path": "", "abi_path": "",
                    "fetched_at": "now", "fetch_errors": [],
                },
            },
        }

        with patch(
            "incident_augmentation.tx_deep_analysis.service.collect_transaction_artifacts",
            return_value=collector_return,
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.run_contract_intelligence",
            return_value=fake_inventory,
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.run_technical_reasoner",
            return_value=_good_reasoning_for("0xaaa"),
        ):
            result = run_incident_technical_analysis(
                seed=seed, run_dir=run_dir, source_context={"summary": "s"},
            )

        # Planner + inventory artifacts land on disk
        assert (run_dir / "analysis_plan.json").exists()
        plan = json.loads((run_dir / "analysis_plan.json").read_text())
        assert "0xrouter" in plan["roles"]["routers"]

        # Final payload has the three new top-level keys + semantic_checks
        payload = json.loads((run_dir / "technical_analysis.json").read_text())
        assert "analysis_plan" in payload
        assert "contract_inventory" in payload
        assert payload["contract_inventory"]["contracts"]["0xrouter"]["contract_name"] == "UniswapV2Router"
        assert payload["revision_round"] == 0
        validation = payload["validation"]
        assert "severity" in validation
        assert set(validation["semantic_checks"].keys()) == {
            "tx_role_consistency", "funds_flow_consistency", "mechanism_source_consistency",
        }
        assert validation["severity"] in {"pass", "warn", "critical"}
        assert result["status"] == "completed"

    def test_revision_loop_runs_at_most_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from incident_augmentation.tx_deep_analysis.service import run_incident_technical_analysis

        seed = IncidentSeed.from_dict({
            "incident_id": "stage2-revision-2026",
            "job_id": "job",
            "trigger_type": "api",
            "seed_type": "manual",
            "chain": "eth",
            "protocol_name": "Stage2 Revision",
            "incident_name": "Stage2 Revision Incident",
            "incident_date": "2026-04-20",
            "attack_tx_hashes": ["0xbbb"],
            "seed_urls": [],
            "summary_candidates": ["Revision loop test."],
        })
        run_dir = tmp_path / seed.incident_id
        run_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CAPSTONE_RPC_ETH", "https://rpc.example")

        tx_dir = run_dir / "technical_analysis" / "0xbbb"
        collector_return = self._prepare_collector_with_real_artifacts(tx_hash="0xbbb", tx_dir=tx_dir)

        # First reasoner call: BAD (claims flash_loan_trigger, trace has no flash loan)
        # Second reasoner call: GOOD (corrected to swap_trigger, which the trace supports)
        with patch(
            "incident_augmentation.tx_deep_analysis.service.collect_transaction_artifacts",
            return_value=collector_return,
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.run_contract_intelligence",
            return_value={"contracts": {}},
        ), patch(
            "incident_augmentation.tx_deep_analysis.service.run_technical_reasoner",
            side_effect=[_bad_reasoning_for("0xbbb"), _good_reasoning_for("0xbbb")],
        ) as reasoner_mock:
            result = run_incident_technical_analysis(
                seed=seed, run_dir=run_dir, source_context={"summary": "s"},
            )

        # Revision should fire exactly once → exactly 2 reasoner calls.
        assert reasoner_mock.call_count == 2
        # The second call must have carried the revision_critique kwarg.
        second_call_kwargs = reasoner_mock.call_args_list[1].kwargs
        assert second_call_kwargs.get("revision_critique"), (
            "second reasoner call should receive a non-empty revision_critique"
        )
        # Final payload reflects the corrected reasoning and revision_round=1.
        assert result["reasoning"]["tx_role_map"] == {"0xbbb": "swap_trigger"}
        assert result["revision_round"] == 1
        assert result["validation"]["severity"] in {"pass", "warn"}
        assert result["validation"]["needs_revision"] is False


def test_load_external_enrichment_unavailable_when_no_cache(tmp_path: Path) -> None:
    from incident_augmentation.tx_deep_analysis.service import _load_external_enrichment

    result = _load_external_enrichment(tmp_path)
    assert result["status"] == "unavailable"
    assert result["reason"] == "cache_not_found"


def test_load_external_enrichment_empty_when_no_endpoint_data(tmp_path: Path) -> None:
    from incident_augmentation.tx_deep_analysis.service import _load_external_enrichment

    (tmp_path / "external_enrichment.json").write_text(json.dumps({
        "tx_hash": "0xdead",
        "chain": "eth",
        "endpoints": {},
    }))
    result = _load_external_enrichment(tmp_path)
    assert result["status"] == "empty"


def test_load_external_enrichment_normalizes_endpoint_payload(tmp_path: Path) -> None:
    from incident_augmentation.tx_deep_analysis.service import _load_external_enrichment

    (tmp_path / "external_enrichment.json").write_text(json.dumps({
        "tx_hash": "0xdead",
        "chain": "eth",
        "endpoints": {
            "explorer/v2/onchain/tx/address-label": {
                "labels": [{"address": "0xaaa", "label": "Aave: Pool V3"}],
            },
            "explorer/v2/onchain/tx/balance-change": {
                "balanceChanges": [{"address": "0xaaa", "usdValue": 41746}],
            },
            "explorer/v2/onchain/tx/state-change": {
                "stateChanges": [{"slot": "0x0", "before": "0x1", "after": "0x2"}],
            },
            "explorer/v2/onchain/tx/fundflow": {
                "transfers": [{"from": "0xa", "to": "0xb", "amount": "100"}],
            },
        },
    }))
    result = _load_external_enrichment(tmp_path)
    assert result["status"] == "loaded"
    assert result["tx_hash"] == "0xdead"
    assert len(result["address_labels"]) == 1
    assert result["balance_changes"][0]["usdValue"] == 41746
    assert len(result["state_changes"]) == 1
    assert len(result["fund_transfers"]) == 1

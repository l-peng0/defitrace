from __future__ import annotations

import json
from pathlib import Path

from incident_augmentation.tx_deep_analysis.validator import validate_technical_analysis


def _write(path: Path, payload) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return str(path)


def _base_reasoning(**overrides) -> dict:
    base = {
        "attack_flow_summary": "",
        "exploit_mechanism": "",
        "tx_role_map": {},
        "contract_role_map": {},
        "timeline_steps": [],
        "funds_flow_path": [],
        "open_questions": [],
        "confidence_notes": [],
    }
    base.update(overrides)
    return base


class TestTxRoleConsistency:
    def test_flags_missing_flashloan_selector(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [
            {"selector_category": "swap", "to": "0xrouter", "from": "0xeoa"},
        ])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(
                exploit_mechanism="some attack",
                tx_role_map={"0xtx1": "flash_loan_trigger"},
            ),
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["severity"] == "critical"
        assert result["needs_revision"] is True
        assert "flash_loan_trigger" in result["revision_request"]
        assert result["semantic_checks"]["tx_role_consistency"]["status"] == "fail"

    def test_passes_when_flashloan_selector_present(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [
            {"selector_category": "flashloan", "to": "0xaave", "from": "0xeoa"},
        ])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(tx_role_map={"0xtx1": "flash_loan_trigger"}),
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["semantic_checks"]["tx_role_consistency"]["status"] == "pass"
        assert result["severity"] == "pass"
        assert result["needs_revision"] is False


class TestFundsFlowConsistency:
    def test_flags_phantom_transfer(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [])
        flow_path = _write(tmp_path / "flow.json", {
            "native_transfers": [],
            "token_transfers": [
                {"token": "0xusdc", "from": "0xa", "to": "0xb", "value": 1000},
            ],
        })
        claim = "0xdeaddeaddeaddeaddeaddeaddeaddeaddeaddead→0xbeefbeefbeefbeefbeefbeefbeefbeefbeefbeef: 500 USDC"
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(funds_flow_path=[claim]),
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["semantic_checks"]["funds_flow_consistency"]["status"] == "fail"
        assert result["severity"] == "critical"
        assert result["needs_revision"] is True

    def test_narrative_entry_is_ignored(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(
                funds_flow_path=["Attacker drained the lending pool via repeated swaps."],
            ),
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["semantic_checks"]["funds_flow_consistency"]["status"] == "pass"


class TestMechanismSourceConsistency:
    def test_warns_when_oracle_mentioned_but_absent_in_inventory(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(
                exploit_mechanism="Attacker manipulated the oracle price feed.",
            ),
            "contract_inventory": {"contracts": {
                "0xrouter": {"contract_name": "UniswapV2Router", "role": "router"},
            }},
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["semantic_checks"]["mechanism_source_consistency"]["status"] == "warn"
        assert result["severity"] == "warn"
        # warn-only must NOT trigger revision
        assert result["needs_revision"] is False

    def test_passes_when_oracle_contract_present(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(
                exploit_mechanism="Oracle was manipulated to mispricing.",
            ),
            "contract_inventory": {"contracts": {
                "0xoracle": {"contract_name": "ChainlinkOracle", "role": "oracle"},
            }},
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert result["semantic_checks"]["mechanism_source_consistency"]["status"] == "pass"


class TestRevisionRoundGate:
    def test_revision_round_1_does_not_loop(self, tmp_path: Path) -> None:
        decoded_path = _write(tmp_path / "decoded.json", [
            {"selector_category": "swap", "to": "0xrouter", "from": "0xeoa"},
        ])
        flow_path = _write(tmp_path / "flow.json", {"native_transfers": [], "token_transfers": []})
        # Same critical-triggering payload as the first test, but revision_round=1
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [
                {"tx_hash": "0xtx1", "status": "completed", "issues": [],
                 "decoded_calls_path": decoded_path, "funds_flow_path": flow_path},
            ],
            "reasoning": _base_reasoning(tx_role_map={"0xtx1": "flash_loan_trigger"}),
            "status": "completed",
            "revision_round": 1,
        }
        result = validate_technical_analysis(payload)
        assert result["severity"] == "critical"
        assert result["needs_revision"] is False
        assert result["revision_request"] == ""


class TestBackwardCompatibility:
    def test_legacy_payload_still_returns_expected_fields(self) -> None:
        payload = {
            "tx_hashes": ["0xtx1"],
            "transactions": [{"tx_hash": "0xtx1", "status": "completed", "issues": []}],
            "reasoning": _base_reasoning(),
            "status": "completed",
        }
        result = validate_technical_analysis(payload)
        assert "verdict" in result
        assert "unresolved_gaps" in result
        assert "checked_transactions" in result
        assert result["checked_transactions"] == 1
        # new fields must also be present, even on legacy inputs
        assert "severity" in result
        assert "needs_revision" in result
        assert "semantic_checks" in result

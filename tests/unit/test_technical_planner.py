from __future__ import annotations

import json
from pathlib import Path

from incident_augmentation.tx_deep_analysis.planner import run_technical_planner


def _write(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _stub_tx(
    tmp: Path,
    *,
    tx_hash: str,
    tx_from: str,
    decoded: list[dict],
    trace: dict | None,
    token_transfers: list[dict],
) -> dict:
    tx_dir = tmp / tx_hash
    tx_dir.mkdir(parents=True, exist_ok=True)
    _write(tx_dir / "tx.json", {"from": tx_from, "to": "0xaaaa", "value": "0x0"})
    _write(tx_dir / "decoded_calls.json", decoded)
    if trace is not None:
        _write(tx_dir / "trace_callTracer.json", trace)
    _write(tx_dir / "funds_flow.json", {"native_transfers": [], "token_transfers": token_transfers})
    return {
        "tx_hash": tx_hash,
        "status": "completed",
        "tx_path": str(tx_dir / "tx.json"),
        "decoded_calls_path": str(tx_dir / "decoded_calls.json"),
        "trace_path": str(tx_dir / "trace_callTracer.json") if trace is not None else "",
        "funds_flow_path": str(tx_dir / "funds_flow.json"),
    }


class TestTechnicalPlanner:
    def test_detect_create_and_create2_contracts(self, tmp_path: Path) -> None:
        trace = {
            "result": {
                "type": "CALL",
                "from": "0xeoa",
                "to": "0xaaaa",
                "input": "0x",
                "calls": [
                    {"type": "CREATE", "from": "0xaaaa", "to": "0xcreate1", "input": "0x"},
                    {
                        "type": "CALL",
                        "from": "0xaaaa",
                        "to": "0xrouter",
                        "input": "0x38ed1739",
                        "calls": [
                            {"type": "CREATE2", "from": "0xrouter", "to": "0xcreate2", "input": "0x"},
                        ],
                    },
                ],
            }
        }
        txs = [_stub_tx(tmp_path, tx_hash="0xtx1", tx_from="0xeoa", decoded=[], trace=trace, token_transfers=[])]
        plan = run_technical_planner(
            incident_id="inc",
            chain="eth",
            transactions=txs,
            output_dir=tmp_path,
        )
        assert "0xcreate1" in plan["roles"]["attacker_contracts"]
        assert "0xcreate2" in plan["roles"]["attacker_contracts"]
        create_types = {entry["create_type"] for entry in plan["newly_deployed"]}
        assert create_types == {"CREATE", "CREATE2"}
        assert (tmp_path / "analysis_plan.json").exists()

    def test_role_classification_from_swap_selectors(self, tmp_path: Path) -> None:
        decoded = [
            {
                "path": "0", "depth": 0, "type": "CALL",
                "from": "0xeoa", "to": "0xrouter",
                "selector": "0x38ed1739", "selector_category": "swap",
                "value": 0,
            },
            {
                "path": "0.0", "depth": 1, "type": "CALL",
                "from": "0xrouter", "to": "0xpair",
                "selector": "0x022c0d9f", "selector_category": "swap",
                "value": 0,
            },
            {
                "path": "0.1", "depth": 1, "type": "CALL",
                "from": "0xrouter", "to": "0xaave",
                "selector": "0xab9c4b5d", "selector_category": "flashloan",
                "value": 0,
            },
        ]
        txs = [_stub_tx(tmp_path, tx_hash="0xtx1", tx_from="0xeoa", decoded=decoded, trace=None, token_transfers=[])]
        plan = run_technical_planner(
            incident_id="inc",
            chain="eth",
            transactions=txs,
            output_dir=tmp_path,
        )
        assert "0xrouter" in plan["roles"]["routers"]
        assert "0xpair" in plan["roles"]["pairs"]
        assert "0xaave" in plan["roles"]["flash_loan_providers"]
        # 0xpair qualifies for both routers and pairs; planner should dedupe out of routers.
        assert "0xpair" not in plan["roles"]["routers"]

    def test_victim_is_largest_net_loser(self, tmp_path: Path) -> None:
        token_transfers = [
            {"token": "0xusdc", "from": "0xvictim", "to": "0xeoa", "value": 1_000_000},
            {"token": "0xusdc", "from": "0xvictim", "to": "0xeoa", "value": 500_000},
            {"token": "0xusdc", "from": "0xbystander", "to": "0xeoa", "value": 1000},
        ]
        txs = [_stub_tx(tmp_path, tx_hash="0xtx1", tx_from="0xeoa", decoded=[], trace=None, token_transfers=token_transfers)]
        plan = run_technical_planner(
            incident_id="inc",
            chain="eth",
            transactions=txs,
            output_dir=tmp_path,
        )
        assert plan["roles"]["victim"] == ["0xvictim"]
        # attacker EOA should not end up as victim even though it's net-positive on the other side
        assert "0xeoa" not in plan["roles"]["victim"]
        # Token shows up
        assert "0xusdc" in plan["roles"]["tokens"]

    def test_empty_when_no_artifacts(self, tmp_path: Path) -> None:
        plan = run_technical_planner(
            incident_id="inc",
            chain="eth",
            transactions=[],
            output_dir=tmp_path,
        )
        assert plan["roles"]["attacker_eoa"] == []
        assert plan["roles"]["victim"] == []
        assert plan["newly_deployed"] == []
        assert plan["priority_contracts"] == []
        assert (tmp_path / "analysis_plan.json").exists()

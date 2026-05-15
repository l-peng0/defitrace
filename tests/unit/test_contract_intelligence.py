from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from incident_augmentation.tx_deep_analysis.contract_intelligence import (
    _extract_minimal_proxy_target,
    detect_proxy,
    fetch_verified_source,
    run_contract_intelligence,
)


def _make_response(json_payload: dict | list, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = RuntimeError(f"status {status_code}")
    return resp


class TestProxyDetection:
    def test_eip1967_proxy_detection(self) -> None:
        impl_word = "0x000000000000000000000000abcdef0123456789abcdef0123456789abcdef01"
        zero_word = "0x" + "0" * 64

        def fake_rpc(url: str, method: str, params: list) -> dict:
            if method == "eth_getStorageAt" and params[1].startswith("0x360894"):
                return {"result": impl_word}
            if method == "eth_getStorageAt" and params[1].startswith("0xb53127"):
                return {"result": zero_word}
            raise AssertionError(f"unexpected RPC call: {method} {params}")

        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.rpc_request",
            side_effect=fake_rpc,
        ):
            result = detect_proxy("https://rpc.example", "0xproxy")

        assert result["is_proxy"] is True
        assert result["proxy_type"] == "EIP-1967"
        assert result["implementation_address"] == "0xabcdef0123456789abcdef0123456789abcdef01"

    def test_minimal_proxy_detection(self) -> None:
        zero_word = "0x" + "0" * 64
        impl = "deadbeefcafebabe0001020304050607080900ab"
        minimal_proxy_code = (
            "0x363d3d373d3d3d363d73"
            + impl
            + "5af43d82803e903d91602b57fd5bf3"
        )

        def fake_rpc(url: str, method: str, params: list) -> dict:
            if method == "eth_getStorageAt":
                return {"result": zero_word}
            if method == "eth_getCode":
                return {"result": minimal_proxy_code}
            raise AssertionError(f"unexpected RPC call: {method}")

        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.rpc_request",
            side_effect=fake_rpc,
        ):
            result = detect_proxy("https://rpc.example", "0xcloner")

        assert result["is_proxy"] is True
        assert result["proxy_type"] == "minimal_proxy"
        assert result["implementation_address"] == "0x" + impl

    def test_not_a_proxy(self) -> None:
        zero_word = "0x" + "0" * 64

        def fake_rpc(url: str, method: str, params: list) -> dict:
            if method == "eth_getStorageAt":
                return {"result": zero_word}
            if method == "eth_getCode":
                return {"result": "0x608060405234801561001057600080fd"}
            raise AssertionError(f"unexpected RPC: {method}")

        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.rpc_request",
            side_effect=fake_rpc,
        ):
            result = detect_proxy("https://rpc.example", "0xplain")

        assert result["is_proxy"] is False
        assert result["implementation_address"] == ""

    def test_extract_minimal_proxy_target_rejects_zero_impl(self) -> None:
        zero_impl_code = (
            "0x363d3d373d3d3d363d73"
            + "0" * 40
            + "5af43d82803e903d91602b57fd5bf3"
        )
        assert _extract_minimal_proxy_target(zero_impl_code) == ""


class TestVerifiedSourceFetch:
    def test_verified_source_cached_to_disk(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ETHERSCAN_API_KEY", "fake")
        api_payload = {
            "status": "1",
            "result": [
                {
                    "SourceCode": "contract X { }",
                    "ContractName": "MyContract",
                    "CompilerVersion": "v0.8.19+commit.7dd6d404",
                    "ABI": json.dumps([{"type": "function", "name": "foo"}]),
                }
            ],
        }

        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.requests.get",
            return_value=_make_response(api_payload),
        ):
            info = fetch_verified_source(chain="eth", address="0xabc", contracts_root=tmp_path)

        assert info["classification"] == "verified"
        assert info["contract_name"] == "MyContract"
        assert (tmp_path / "0xabc" / "source.json").exists()
        assert (tmp_path / "0xabc" / "abi.json").exists()
        # cache hit on second call — we should not hit HTTP again
        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.requests.get",
            side_effect=AssertionError("should not re-fetch"),
        ):
            second = fetch_verified_source(chain="eth", address="0xabc", contracts_root=tmp_path)
        assert second["classification"] == "verified"
        assert second.get("cache_hit") is True

    def test_unverified_when_source_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ETHERSCAN_API_KEY", "fake")
        api_payload = {
            "status": "0",
            "result": [
                {
                    "SourceCode": "",
                    "ContractName": "",
                    "CompilerVersion": "",
                    "ABI": "Contract source code not verified",
                }
            ],
        }
        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.requests.get",
            return_value=_make_response(api_payload),
        ):
            info = fetch_verified_source(chain="eth", address="0xdef", contracts_root=tmp_path)
        assert info["classification"] == "unverified"
        # source.json is still written so we don't re-hit on next run
        assert (tmp_path / "0xdef" / "source.json").exists()
        assert info.get("abi_path", "") == ""

    def test_rate_limit_retry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ETHERSCAN_API_KEY", "fake")
        good_payload = {
            "status": "1",
            "result": [
                {
                    "SourceCode": "contract Y { }",
                    "ContractName": "Y",
                    "CompilerVersion": "v0.8.0",
                    "ABI": "[]",
                }
            ],
        }
        responses = [_make_response({}, status_code=429), _make_response(good_payload)]
        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.requests.get",
            side_effect=responses,
        ), patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.time.sleep",
            return_value=None,
        ):
            info = fetch_verified_source(chain="eth", address="0xghi", contracts_root=tmp_path)
        assert info["classification"] == "verified"
        assert info["fetch_errors"] == []

    def test_no_api_key_fails_cleanly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
        info = fetch_verified_source(chain="eth", address="0xno_key", contracts_root=tmp_path)
        assert info["classification"] == "failed"
        assert any("ETHERSCAN_API_KEY" in err for err in info["fetch_errors"])


class TestRunContractIntelligence:
    def test_newly_deployed_contracts_are_marked_unverified(self, tmp_path: Path) -> None:
        plan = {
            "priority_contracts": [
                {"address": "0xrouter", "role": "router", "priority": "medium"},
            ],
            "newly_deployed": [
                {"address": "0xattacker", "deployed_by": "0xeoa", "create_type": "CREATE2",
                 "tx_hash": "0xtx"},
            ],
        }
        zero_word = "0x" + "0" * 64

        def fake_rpc(url: str, method: str, params: list) -> dict:
            if method == "eth_getStorageAt":
                return {"result": zero_word}
            if method == "eth_getCode":
                return {"result": "0x00"}
            raise AssertionError(f"unexpected RPC: {method}")

        def fake_fetch(*, chain: str, address: str, contracts_root: Path) -> dict:
            return {
                "classification": "verified" if address == "0xrouter" else "unverified",
                "contract_name": "Router" if address == "0xrouter" else "",
                "compiler_version": "",
                "source_path": str(contracts_root / address / "source.json"),
                "abi_path": "",
                "fetched_at": "now",
                "fetch_errors": [],
            }

        with patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.rpc_request",
            side_effect=fake_rpc,
        ), patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.fetch_verified_source",
            side_effect=fake_fetch,
        ), patch(
            "incident_augmentation.tx_deep_analysis.contract_intelligence.time.sleep",
            return_value=None,
        ):
            inventory = run_contract_intelligence(
                incident_id="inc",
                chain="eth",
                rpc_url="https://rpc",
                plan=plan,
                output_dir=tmp_path,
            )

        contracts = inventory["contracts"]
        assert "0xrouter" in contracts
        assert contracts["0xrouter"]["classification"] == "verified"
        assert contracts["0xrouter"]["contract_name"] == "Router"

        # Newly-deployed contract: no RPC probe, no source fetch — just marked.
        assert "0xattacker" in contracts
        assert contracts["0xattacker"]["classification"] == "unverified"
        assert contracts["0xattacker"]["create_type"] == "CREATE2"
        assert contracts["0xattacker"]["newly_deployed_in_tx"] == "0xtx"
        assert any(
            "newly deployed in-tx" in err
            for err in contracts["0xattacker"]["fetch_errors"]
        )
        assert (tmp_path / "contract_inventory.json").exists()

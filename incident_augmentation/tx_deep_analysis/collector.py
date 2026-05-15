from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

from .decoder import decode_trace_calls, summarize_funds_flow

logger = logging.getLogger(__name__)


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def rpc_request(rpc_url: str, method: str, params: list[Any]) -> dict[str, Any]:
    response = requests.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"{method} failed: {payload['error']}")
    return payload


def collect_transaction_artifacts(tx_hash: str, chain: str, rpc_url: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []

    tx_path = output_dir / "tx.json"
    receipt_path = output_dir / "receipt.json"
    trace_path = output_dir / "trace_callTracer.json"
    decoded_calls_path = output_dir / "decoded_calls.json"
    funds_flow_path = output_dir / "funds_flow.json"
    manifest_path = output_dir / "manifest.json"

    tx_payload: dict[str, Any] | None = None
    receipt_payload: dict[str, Any] | None = None
    trace_payload: dict[str, Any] | None = None
    decoded_calls: list[dict[str, Any]] = []
    funds_flow: dict[str, Any] = {"native_transfers": [], "token_transfers": [], "summary": {}}

    try:
        tx_payload = rpc_request(rpc_url, "eth_getTransactionByHash", [tx_hash]).get("result")
        if not tx_payload:
            raise RuntimeError("transaction not found")
        _write_json(tx_path, tx_payload)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"tx fetch failed: {exc}")

    try:
        receipt_payload = rpc_request(rpc_url, "eth_getTransactionReceipt", [tx_hash]).get("result")
        if not receipt_payload:
            raise RuntimeError("receipt not found")
        _write_json(receipt_path, receipt_payload)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"receipt fetch failed: {exc}")

    try:
        trace_payload = rpc_request(
            rpc_url,
            "debug_traceTransaction",
            [tx_hash, {"tracer": "callTracer"}],
        )
        _write_json(trace_path, trace_payload)
        decoded_calls = decode_trace_calls(trace_payload)
        _write_json(decoded_calls_path, decoded_calls)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"trace fetch failed: {exc}")

    if tx_payload or receipt_payload:
        funds_flow = summarize_funds_flow(tx_payload, receipt_payload)
        _write_json(funds_flow_path, funds_flow)

    contracts_touched = sorted(
        {
            str(call.get("to", ""))
            for call in decoded_calls
            if call.get("to")
        }
    )
    addresses_seen = sorted(
        {
            value
            for value in [
                *(call.get("from", "") for call in decoded_calls),
                *(call.get("to", "") for call in decoded_calls),
                tx_payload.get("from", "") if tx_payload else "",
                tx_payload.get("to", "") if tx_payload else "",
            ]
            if value
        }
    )

    status = "completed"
    if issues:
        status = "partial" if tx_payload or receipt_payload else "failed"

    manifest = {
        "tx_hash": tx_hash,
        "chain": chain,
        "status": status,
        "files": {
            "tx": str(tx_path) if tx_path.exists() else "",
            "receipt": str(receipt_path) if receipt_path.exists() else "",
            "trace_callTracer": str(trace_path) if trace_path.exists() else "",
            "decoded_calls": str(decoded_calls_path) if decoded_calls_path.exists() else "",
            "funds_flow": str(funds_flow_path) if funds_flow_path.exists() else "",
        },
        "summary": {
            "contracts_touched": contracts_touched,
            "addresses_seen": addresses_seen,
            "native_value_transfers": funds_flow.get("summary", {}).get("native_value_transfers", 0),
            "token_transfers": funds_flow.get("summary", {}).get("token_transfers", 0),
        },
        "issues": issues,
    }
    _write_json(manifest_path, manifest)

    return {
        "tx_hash": tx_hash,
        "status": status,
        "tx_path": str(tx_path) if tx_path.exists() else "",
        "receipt_path": str(receipt_path) if receipt_path.exists() else "",
        "trace_path": str(trace_path) if trace_path.exists() else "",
        "decoded_calls_path": str(decoded_calls_path) if decoded_calls_path.exists() else "",
        "funds_flow_path": str(funds_flow_path) if funds_flow_path.exists() else "",
        "manifest_path": str(manifest_path),
        "summary": manifest["summary"],
        "issues": issues,
    }

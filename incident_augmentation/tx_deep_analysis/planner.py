"""Rule-based investigation planner.

Reads the deterministic artifacts each transaction's collector wrote
(`decoded_calls.json`, `funds_flow.json`, `trace_callTracer.json`) and
produces a pre-reasoning `analysis_plan.json` that labels addresses by
role and flags contracts the downstream stages should focus on.

No LLM calls. All heuristics are rule-based so the plan is
deterministic and reproducible across runs.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from incident_augmentation.models import utc_now_iso

from .decoder import detect_created_contracts

logger = logging.getLogger(__name__)


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _load_json(path: str | Path) -> Any:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _unique_ordered(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = (raw or "").lower().strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def run_technical_planner(
    *,
    incident_id: str,
    chain: str,
    transactions: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    """Classify addresses touched by the incident's transactions into roles.

    Arguments mirror the shape `service.run_incident_technical_analysis()`
    already builds — each item in `transactions` is the dict returned by
    `collect_transaction_artifacts`. `output_dir` is the per-incident run
    directory; the plan is written to `output_dir / analysis_plan.json`.
    """
    tx_hashes = [item.get("tx_hash", "") for item in transactions if item.get("tx_hash")]

    attacker_eoa: set[str] = set()
    attacker_contracts: set[str] = set()
    routers: set[str] = set()
    pairs: set[str] = set()
    flash_loan_providers: set[str] = set()
    tokens: set[str] = set()
    touched: set[str] = set()

    newly_deployed: list[dict[str, Any]] = []
    net_token_balances: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    investigation_notes: list[str] = []
    call_graph_edges: list[dict[str, str]] = []
    call_graph_seen: set[tuple[str, str, str]] = set()

    for item in transactions:
        tx_hash = item.get("tx_hash", "")
        decoded = _load_json(item.get("decoded_calls_path", "")) or []
        trace = _load_json(item.get("trace_path", ""))
        funds_flow = _load_json(item.get("funds_flow_path", "")) or {}
        tx = _load_json(item.get("tx_path", "")) or {}

        # Attacker EOA = the tx originator.
        tx_from = str(tx.get("from") or "").lower()
        if tx_from:
            attacker_eoa.add(tx_from)

        # CREATE/CREATE2 deployments → attacker contracts.
        created = detect_created_contracts(trace) if trace else []
        for entry in created:
            entry_with_tx = {**entry, "tx_hash": tx_hash}
            newly_deployed.append(entry_with_tx)
            attacker_contracts.add(entry["address"])

        # Walk decoded calls once.
        swap_count = 0
        for call in decoded:
            from_addr = str(call.get("from", "") or "").lower()
            to_addr = str(call.get("to", "") or "").lower()
            if from_addr:
                touched.add(from_addr)
            if to_addr:
                touched.add(to_addr)

            category = call.get("selector_category", "")
            if category == "swap" and to_addr:
                routers.add(to_addr)
                swap_count += 1
                # Uniswap V2 pair swap (0x022c0d9f) directly targets the pair.
                if call.get("selector") == "0x022c0d9f":
                    pairs.add(to_addr)
            elif category == "flashloan" and to_addr:
                flash_loan_providers.add(to_addr)

            # Capture meaningful edges for the frontend graph. Skip untyped
            # "other" and "read" to keep the edge set small.
            if category in {"swap", "flashloan", "transfer", "mint", "burn"} and from_addr and to_addr:
                key = (from_addr, to_addr, category)
                if key not in call_graph_seen and len(call_graph_edges) < 40:
                    call_graph_seen.add(key)
                    call_graph_edges.append(
                        {"from": from_addr, "to": to_addr, "category": category}
                    )

        if swap_count:
            investigation_notes.append(
                f"Tx {tx_hash} contains {swap_count} swap selector(s); inspect router/pair pricing."
            )

        # Token addresses = whatever emitted an ERC-20 Transfer.
        for transfer in funds_flow.get("token_transfers", []) or []:
            token = str(transfer.get("token") or "").lower()
            if token:
                tokens.add(token)
            holder_from = str(transfer.get("from") or "").lower()
            holder_to = str(transfer.get("to") or "").lower()
            value_wei = int(transfer.get("value") or 0)
            if holder_from and value_wei:
                net_token_balances[holder_from][token] -= value_wei
            if holder_to and value_wei:
                net_token_balances[holder_to][token] += value_wei
            if holder_from:
                touched.add(holder_from)
            if holder_to:
                touched.add(holder_to)

    # Victim = the address with the largest net-negative exposure across
    # *all* tokens in this incident. "Largest" is measured on unit wei,
    # not USD — we don't have price data here. This is intentionally
    # conservative and approximate.
    victim: list[str] = []
    if net_token_balances:
        def net_loss_score(addr: str) -> int:
            return sum(balance for balance in net_token_balances[addr].values() if balance < 0)

        candidates = [addr for addr in net_token_balances if net_loss_score(addr) < 0]
        # Exclude the attacker EOA and attacker contracts from the victim pool;
        # they also show as net-negative during flash-loan repayment but are
        # not the actual victim.
        candidates = [addr for addr in candidates if addr not in attacker_eoa and addr not in attacker_contracts]
        if candidates:
            candidates.sort(key=net_loss_score)  # most negative first
            victim = [candidates[0]]

    roles_index: dict[str, str] = {}
    def assign(addrs: Iterable[str], role: str) -> None:
        for addr in addrs:
            if addr and addr not in roles_index:
                roles_index[addr] = role

    # Priority order matters when an address qualifies for several buckets.
    assign(attacker_eoa, "attacker_eoa")
    assign(attacker_contracts, "attacker_contract")
    assign(victim, "victim")
    assign(flash_loan_providers, "flash_loan_provider")
    assign(pairs, "pair")
    assign(routers, "router")
    assign(tokens, "token")

    unknown = [addr for addr in touched if addr not in roles_index]

    roles = {
        "attacker_eoa": _unique_ordered(attacker_eoa),
        "attacker_contracts": _unique_ordered(attacker_contracts),
        "victim": _unique_ordered(victim),
        "routers": _unique_ordered(r for r in routers if r not in pairs),
        "pairs": _unique_ordered(pairs),
        "oracles": [],
        "flash_loan_providers": _unique_ordered(flash_loan_providers),
        "tokens": _unique_ordered(t for t in tokens if t not in attacker_contracts),
        "unknown": _unique_ordered(unknown),
    }

    priority_contracts: list[dict[str, Any]] = []
    for address in roles["attacker_contracts"]:
        priority_contracts.append(
            {
                "address": address,
                "role": "attacker_contract",
                "why": "deployed in-tx via CREATE/CREATE2",
                "priority": "high",
            }
        )
    for address in roles["victim"]:
        priority_contracts.append(
            {
                "address": address,
                "role": "victim",
                "why": "largest net-negative token balance change",
                "priority": "high",
            }
        )
    for address in roles["pairs"]:
        priority_contracts.append(
            {
                "address": address,
                "role": "pair",
                "why": "target of direct swap()",
                "priority": "medium",
            }
        )
    for address in roles["routers"]:
        priority_contracts.append(
            {
                "address": address,
                "role": "router",
                "why": "called with swap* selector",
                "priority": "medium",
            }
        )
    for address in roles["flash_loan_providers"]:
        priority_contracts.append(
            {
                "address": address,
                "role": "flash_loan_provider",
                "why": "called with flashLoan* selector",
                "priority": "medium",
            }
        )

    plan = {
        "incident_id": incident_id,
        "chain": chain,
        "generated_at": utc_now_iso(),
        "tx_hashes": tx_hashes,
        "roles": roles,
        "newly_deployed": newly_deployed,
        "priority_contracts": priority_contracts,
        "investigation_notes": investigation_notes,
        "call_graph": call_graph_edges,
    }

    _write_json(output_dir / "analysis_plan.json", plan)
    logger.info(
        "technical.planner_done",
        extra={
            "incident_id": incident_id,
            "priority_contracts": len(priority_contracts),
            "newly_deployed": len(newly_deployed),
        },
    )
    return plan

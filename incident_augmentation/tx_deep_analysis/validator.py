"""Semantic + structural validation for `technical_analysis.json`.

Previously this module only did structural checks (required keys, tx hash
references). It now also does three semantic cross-checks against the
deterministic artifacts, and emits a `severity` + `needs_revision` +
`revision_request` payload the orchestrator can use to trigger a single
reasoner revision pass.

All semantic checks are deterministic Python — no LLM calls. The
`revision_request` string is also deterministic (a concatenation of
specific findings), so the same input always produces the same output.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Keywords that, when mentioned in exploit_mechanism, expect a corresponding
# contract in the inventory.
_MECHANISM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "oracle": ("oracle",),
    "flashloan": ("flashloan", "flash loan"),
    "reentrancy": ("reentrancy", "reentrant"),
    "delegatecall": ("delegatecall",),
}

# tx_role_map role → required evidence category in decoded calls.
_ROLE_REQUIRED_CATEGORY: dict[str, str] = {
    "flash_loan_trigger": "flashloan",
    "flash_loan_provider": "flashloan",
    "swap_trigger": "swap",
    "swap_execution": "swap",
}

# Regex for `"A→B: N TOKEN"` (or plain ASCII `->`) in funds_flow_path.
_FLOW_ENTRY_RE = re.compile(
    r"""
    ^\s*
    (?P<src>0x[0-9a-fA-F]{40})         # 40-char hex address
    \s*(?:→|->)\s*
    (?P<dst>0x[0-9a-fA-F]{40})
    \s*:\s*
    (?P<amount>[\d_,\.]+)
    \s*
    (?P<token>\S+)?
    """,
    re.VERBOSE,
)


def _load_json(path: str | Path | None) -> Any:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _lower(value: Any) -> str:
    return str(value or "").lower()


def _structural_check(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (unresolved_gaps, structural_errors) — the pre-existing checks."""
    unresolved_gaps: list[str] = []
    structural_errors: list[str] = []

    tx_hashes = payload.get("tx_hashes") or []
    tx_lookup = {item.get("tx_hash", "") for item in payload.get("transactions") or []}

    for tx_item in payload.get("transactions") or []:
        for issue in tx_item.get("issues") or []:
            unresolved_gaps.append(f"{tx_item.get('tx_hash', '')}: {issue}")

    reasoning = payload.get("reasoning") or {}
    for tx_hash in reasoning.get("tx_role_map") or {}:
        if tx_hash not in tx_lookup and tx_hash not in tx_hashes:
            unresolved_gaps.append(f"reasoning referenced unknown tx hash {tx_hash}")

    required_reasoning_keys = {
        "attack_flow_summary",
        "exploit_mechanism",
        "tx_role_map",
        "contract_role_map",
        "timeline_steps",
        "funds_flow_path",
        "open_questions",
        "confidence_notes",
    }
    missing_keys = sorted(key for key in required_reasoning_keys if key not in reasoning)
    if missing_keys:
        structural_errors.append(f"reasoning missing keys: {', '.join(missing_keys)}")

    return unresolved_gaps, structural_errors


def _check_tx_role_consistency(
    *,
    reasoning: dict[str, Any],
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """For each (tx_hash, role) in tx_role_map, require evidence in trace/flow."""
    mismatches: list[dict[str, Any]] = []
    tx_role_map = reasoning.get("tx_role_map") or {}

    for tx_hash, role in tx_role_map.items():
        role_str = _lower(role)
        matched_tx = next((t for t in transactions if _lower(t.get("tx_hash")) == _lower(tx_hash)), None)
        if not matched_tx:
            mismatches.append(
                {
                    "tx_hash": tx_hash,
                    "claimed_role": role_str,
                    "finding": "tx hash not in deterministic transactions list",
                }
            )
            continue

        decoded = _load_json(matched_tx.get("decoded_calls_path")) or []
        funds_flow = _load_json(matched_tx.get("funds_flow_path")) or {}

        required_category = next(
            (cat for role_prefix, cat in _ROLE_REQUIRED_CATEGORY.items()
             if role_str.startswith(role_prefix)),
            "",
        )
        if required_category:
            observed = {_lower(call.get("selector_category")) for call in decoded}
            if required_category not in observed:
                mismatches.append(
                    {
                        "tx_hash": tx_hash,
                        "claimed_role": role_str,
                        "finding": f"no {required_category} selector observed in decoded calls",
                    }
                )
                continue

        if role_str.startswith("drain"):
            claimed_address = role_str.split(":", 1)[-1].strip() if ":" in role_str else ""
            receivers = {_lower(t.get("to")) for t in funds_flow.get("token_transfers", [])}
            if claimed_address and claimed_address not in receivers:
                mismatches.append(
                    {
                        "tx_hash": tx_hash,
                        "claimed_role": role_str,
                        "finding": f"{claimed_address} was not a token transfer recipient",
                    }
                )

    status = "fail" if mismatches else "pass"
    return {"status": status, "mismatches": mismatches}


def _check_funds_flow_consistency(
    *,
    reasoning: dict[str, Any],
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    """For each `A→B: N TOKEN` entry in funds_flow_path, require a matching transfer.

    Narrative entries that don't match the parsable pattern are skipped —
    the check is lenient on prose and strict on claims it can check.
    """
    mismatches: list[dict[str, Any]] = []
    claims = reasoning.get("funds_flow_path") or []

    # Build a combined lookup of observed (from, to, token) across all txs.
    observed_transfers: list[tuple[str, str, str, int]] = []
    for tx in transactions:
        flow = _load_json(tx.get("funds_flow_path")) or {}
        for transfer in flow.get("token_transfers", []) or []:
            observed_transfers.append(
                (
                    _lower(transfer.get("from")),
                    _lower(transfer.get("to")),
                    _lower(transfer.get("token")),
                    int(transfer.get("value") or 0),
                )
            )
        for transfer in flow.get("native_transfers", []) or []:
            observed_transfers.append(
                (
                    _lower(transfer.get("from")),
                    _lower(transfer.get("to")),
                    "native",
                    int(transfer.get("value") or 0),
                )
            )

    for entry in claims:
        claim_text = ""
        claim_from = ""
        claim_to = ""
        claim_token = ""
        if isinstance(entry, dict):
            claim_text = str(entry.get("detail") or entry.get("title") or entry)
            claim_from = _lower(entry.get("from"))
            claim_to = _lower(entry.get("to"))
            claim_token = _lower(entry.get("token"))
        else:
            claim_text = str(entry or "")

        if claim_from and claim_to:
            src = claim_from
            dst = claim_to
            token_label = claim_token
        else:
            match = _FLOW_ENTRY_RE.match(claim_text)
            if not match:
                continue  # narrative entry, skip
            src = _lower(match.group("src"))
            dst = _lower(match.group("dst"))
            token_label = _lower(match.group("token") or "")

        # Does ANY observed transfer match (src, dst) with a compatible token?
        token_matches = [
            (f, t, tk, v)
            for (f, t, tk, v) in observed_transfers
            if f == src and t == dst and (not token_label or token_label in tk or tk in token_label)
        ]
        if not token_matches:
            mismatches.append(
                {"claim": claim_text, "finding": "no matching transfer observed in funds_flow"}
            )

    status = "fail" if mismatches else "pass"
    return {"status": status, "mismatches": mismatches}


def _check_mechanism_source_consistency(
    *,
    reasoning: dict[str, Any],
    contract_inventory: dict[str, Any],
) -> dict[str, Any]:
    """If exploit_mechanism mentions a technique, require matching evidence in inventory."""
    mismatches: list[dict[str, Any]] = []
    mechanism = _lower(reasoning.get("exploit_mechanism"))
    if not mechanism:
        return {"status": "pass", "mismatches": []}

    inventory_haystack_parts: list[str] = []
    for row in (contract_inventory.get("contracts") or {}).values():
        inventory_haystack_parts.append(_lower(row.get("contract_name")))
        inventory_haystack_parts.append(_lower(row.get("role")))
        # Don't open source.json fully — just the contract name/role is enough
        # of a signal without blowing up token count.
    haystack = " ".join(inventory_haystack_parts)

    for short_key, variants in _MECHANISM_KEYWORDS.items():
        mentioned = any(variant in mechanism for variant in variants)
        if not mentioned:
            continue
        found = any(variant in haystack for variant in variants)
        if not found:
            mismatches.append(
                {
                    "mechanism_mentions": short_key,
                    "finding": f"no contract in inventory has '{short_key}' in its name or role",
                }
            )

    status = "warn" if mismatches else "pass"
    return {"status": status, "mismatches": mismatches}


def _build_revision_request(semantic_checks: dict[str, Any]) -> str:
    parts: list[str] = []
    role_check = semantic_checks.get("tx_role_consistency", {})
    for mismatch in role_check.get("mismatches", []) or []:
        parts.append(
            f"Reasoning assigns role '{mismatch.get('claimed_role')}' to tx "
            f"{mismatch.get('tx_hash')} but {mismatch.get('finding')}. "
            "Revise without assuming this role unless you cite new evidence."
        )
    flow_check = semantic_checks.get("funds_flow_consistency", {})
    for mismatch in flow_check.get("mismatches", []) or []:
        parts.append(
            f"funds_flow_path claims '{mismatch.get('claim')}' which is not observed "
            "in the deterministic funds_flow. Remove or correct this claim."
        )
    return " ".join(parts)


def _semantic_verdict(
    *,
    severity: str,
    final_status: str,
    unresolved_gaps: Iterable[str],
    mismatches_count: int,
) -> str:
    if final_status == "skipped":
        return "Technical analysis was skipped because no configured RPC is available for this chain."
    if final_status == "failed":
        return "Technical analysis failed before a usable deterministic package was built."
    if severity == "critical":
        return f"Semantic validation flagged {mismatches_count} inconsistency(ies) between reasoning and deterministic artifacts."
    if severity == "warn":
        return "Semantic validation raised warnings but no critical mismatches."
    if final_status == "partial" or list(unresolved_gaps):
        return "Technical analysis produced usable partial output, but some deterministic gaps remain."
    return "Deterministic and semantic checks passed."


def validate_technical_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Full-scope validator: structural + semantic + revision-request synthesis.

    Payload shape extensions understood:
      - `transactions[*].decoded_calls_path` — used by tx_role_consistency
      - `transactions[*].funds_flow_path` — used by funds_flow_consistency
      - `contract_inventory` — passed in via `payload['contract_inventory']`
      - `revision_round` — 0 for first pass, 1+ to suppress `needs_revision`

    Backward compatible: callers that pass the old shape still get `verdict`,
    `unresolved_gaps`, and `checked_transactions` in the result.
    """
    unresolved_gaps, structural_errors = _structural_check(payload)
    unresolved_gaps = list(unresolved_gaps) + structural_errors

    reasoning = payload.get("reasoning") or {}
    transactions = payload.get("transactions") or []
    contract_inventory = payload.get("contract_inventory") or {}
    revision_round = int(payload.get("revision_round") or 0)

    semantic_checks = {
        "tx_role_consistency": _check_tx_role_consistency(
            reasoning=reasoning,
            transactions=transactions,
        ),
        "funds_flow_consistency": _check_funds_flow_consistency(
            reasoning=reasoning,
            transactions=transactions,
        ),
        "mechanism_source_consistency": _check_mechanism_source_consistency(
            reasoning=reasoning,
            contract_inventory=contract_inventory,
        ),
    }

    has_fail = any(check.get("status") == "fail" for check in semantic_checks.values())
    has_warn = any(check.get("status") == "warn" for check in semantic_checks.values())

    if has_fail:
        severity = "critical"
    elif has_warn:
        severity = "warn"
    elif unresolved_gaps:
        severity = "warn"
    else:
        severity = "pass"

    final_status = payload.get("status", "skipped")
    needs_revision = severity == "critical" and revision_round == 0 and final_status not in ("skipped", "failed")
    revision_request = _build_revision_request(semantic_checks) if needs_revision else ""

    statuses = {item.get("status", "") for item in transactions}
    mismatches_count = sum(
        len(check.get("mismatches") or []) for check in semantic_checks.values()
    )

    verdict = _semantic_verdict(
        severity=severity,
        final_status=final_status,
        unresolved_gaps=unresolved_gaps,
        mismatches_count=mismatches_count,
    )

    # Don't downgrade severity for partial/failed collection — but surface it.
    if final_status == "partial" and severity == "pass" and (unresolved_gaps or statuses & {"partial", "failed"}):
        severity = "warn"

    return {
        "verdict": verdict,
        "severity": severity,
        "unresolved_gaps": unresolved_gaps,
        "semantic_checks": semantic_checks,
        "needs_revision": needs_revision,
        "revision_request": revision_request,
        "checked_transactions": len(transactions),
    }

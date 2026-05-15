from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from incident_augmentation.agent_trace import TraceCollector
from incident_augmentation.model_runtime import call_llm_with_metadata
from incident_augmentation.models import IncidentSeed, utc_now_iso

from .collector import collect_transaction_artifacts
from .contract_intelligence import run_contract_intelligence
from .planner import run_technical_planner
from .validator import validate_technical_analysis

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ROOT = Path(__file__).resolve().parents[2]
CHAIN_RPC_ENV_KEYS = {
    "eth": "CAPSTONE_RPC_ETH",
    "ethereum": "CAPSTONE_RPC_ETH",
    "bsc": "CAPSTONE_RPC_BSC",
    "bnb": "CAPSTONE_RPC_BSC",
    "arb": "CAPSTONE_RPC_ARB",
    "arbitrum": "CAPSTONE_RPC_ARB",
    "base": "CAPSTONE_RPC_BASE",
    "opt": "CAPSTONE_RPC_OPT",
    "optimism": "CAPSTONE_RPC_OPT",
    "polygon": "CAPSTONE_RPC_POLYGON",
    "avax": "CAPSTONE_RPC_AVAX",
    "avalanche": "CAPSTONE_RPC_AVAX",
}
CHAIN_ALCHEMY_SLUGS = {
    "eth": "eth",
    "ethereum": "eth",
    "bsc": "bnb",
    "bnb": "bnb",
    "arb": "arb",
    "arbitrum": "arb",
    "base": "base",
    "opt": "opt",
    "optimism": "opt",
    "polygon": "polygon",
    "avax": "avax",
    "avalanche": "avax",
}

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional import during bootstrap
    load_dotenv = None

if load_dotenv:
    load_dotenv(ROOT / ".env")


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _rpc_url_for_chain(chain: str) -> str:
    chain_key = str(chain or "").lower()
    env_key = CHAIN_RPC_ENV_KEYS.get(chain_key, "")
    direct_rpc = os.environ.get(env_key, "").strip() if env_key else ""
    if direct_rpc:
        return direct_rpc

    alchemy_key = os.environ.get("ALCHEMY_API_KEY", "").strip()
    alchemy_slug = CHAIN_ALCHEMY_SLUGS.get(chain_key, "")
    if alchemy_key and alchemy_slug:
        return f"https://{alchemy_slug}-mainnet.g.alchemy.com/v2/{alchemy_key}"
    return ""


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _coerce_list_of_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _coerce_list_of_objects(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _coerce_funds_flow_steps(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [{"title": "Fund movement", "detail": value, "tx_hashes": []}] if value.strip() else []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        steps: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                steps.append(item)
            elif str(item).strip():
                steps.append({"title": "Fund movement", "detail": str(item), "tx_hashes": []})
        return steps
    return []


def _normalize_reasoning_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "attack_flow_summary": str(payload.get("attack_flow_summary", "") or ""),
        "exploit_mechanism": str(payload.get("exploit_mechanism", "") or ""),
        "tx_role_map": payload.get("tx_role_map", {}) or {},
        "contract_role_map": payload.get("contract_role_map", {}) or {},
        "timeline_steps": _coerce_list_of_objects(payload.get("timeline_steps", [])),
        "funds_flow_path": _coerce_funds_flow_steps(payload.get("funds_flow_path", [])),
        "open_questions": _coerce_list_of_strings(payload.get("open_questions", [])),
        "confidence_notes": _coerce_list_of_strings(payload.get("confidence_notes", [])),
    }


def _has_reasoning_content(payload: dict[str, Any]) -> bool:
    return any(
        [
            payload.get("attack_flow_summary"),
            payload.get("exploit_mechanism"),
            payload.get("tx_role_map"),
            payload.get("contract_role_map"),
            payload.get("timeline_steps"),
            payload.get("funds_flow_path"),
            payload.get("open_questions"),
            payload.get("confidence_notes"),
        ]
    )


def _json_candidates(text: str) -> list[str]:
    cleaned = _extract_json(text)
    candidates = [cleaned]

    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")
    if object_start != -1 and object_end != -1 and object_end > object_start:
        candidates.append(cleaned[object_start : object_end + 1].strip())

    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")
    if array_start != -1 and array_end != -1 and array_end > array_start:
        candidates.append(cleaned[array_start : array_end + 1].strip())

    unique: list[str] = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
    return unique


def _repair_json_with_llm(
    *,
    incident_id: str,
    raw_text: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    system_prompt = (
        "You repair malformed JSON. Return only valid JSON for the requested schema. "
        "Do not add markdown fences or commentary."
    )
    user_prompt = (
        "Fix the following malformed JSON into a valid object with exactly these keys: "
        "attack_flow_summary, exploit_mechanism, tx_role_map, contract_role_map, "
        "timeline_steps, funds_flow_path, open_questions, confidence_notes.\n\n"
        f"Malformed text:\n{raw_text}"
    )
    repaired = call_llm_with_metadata(system_prompt, user_prompt, incident_id, "technical_reasoner_json_repair")
    for candidate in _json_candidates(repaired["content"]):
        try:
            return _normalize_reasoning_payload(json.loads(candidate)), repaired
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("Could not repair technical reasoning JSON", repaired["content"], 0)


def run_technical_reasoner(
    *,
    incident_id: str,
    seed: IncidentSeed,
    transactions: list[dict[str, Any]],
    source_context: dict[str, Any] | None,
    output_dir: Path,
    analysis_plan: dict[str, Any] | None = None,
    contract_inventory: dict[str, Any] | None = None,
    revision_critique: str = "",
) -> dict[str, Any]:
    template = _load_prompt("technical_reasoner")
    system_prompt = template.split("## System\n", 1)[1].split("\n\n##", 1)[0].strip()
    manifests = [
        {
            "tx_hash": item.get("tx_hash", ""),
            "status": item.get("status", ""),
            "summary": item.get("summary", {}),
            "issues": item.get("issues", []),
        }
        for item in transactions
    ]
    incident_context = {
        "incident_id": incident_id,
        "protocol_name": seed.protocol_name,
        "incident_name": seed.incident_name,
        "chain": seed.chain,
        "summary": (source_context or {}).get("summary", ""),
    }
    plan_payload = analysis_plan or {}
    inventory_payload = contract_inventory or {}
    user_prompt = (
        template.split("## Input\n", 1)[1]
        .replace("{incident_context}", json.dumps(incident_context, ensure_ascii=True))
        .replace("{technical_manifests}", json.dumps(manifests, ensure_ascii=True))
        .replace("{analysis_plan}", json.dumps(plan_payload, ensure_ascii=True))
        .replace("{contract_inventory}", json.dumps(inventory_payload, ensure_ascii=True))
        .replace("{revision_critique}", revision_critique or "(none — this is the first pass)")
    )
    stage_name = "technical_reasoner_revision" if revision_critique else "technical_reasoner"
    llm_result = call_llm_with_metadata(system_prompt, user_prompt, incident_id, stage_name)
    raw_text = llm_result["content"]
    _write_json(
        output_dir / "technical_reasoning_raw.json",
        {
            "incident_id": incident_id,
            "stage": "technical_reasoner",
            "model": llm_result["model"],
            "provider_env": llm_result["api_key_env"],
            "base_url": llm_result["base_url"],
            "raw_text": raw_text,
        },
    )
    for candidate in _json_candidates(raw_text):
        try:
            parsed_raw = json.loads(candidate)
            parsed = _normalize_reasoning_payload(parsed_raw)
            if not _has_reasoning_content(parsed):
                repaired, repaired_meta = _repair_json_with_llm(incident_id=incident_id, raw_text=json.dumps(parsed_raw, ensure_ascii=True))
                _write_json(
                    output_dir / "technical_reasoning_repaired.json",
                    {
                        "incident_id": incident_id,
                        "stage": "technical_reasoner_json_repair",
                        "model": repaired_meta["model"],
                        "provider_env": repaired_meta["api_key_env"],
                        "base_url": repaired_meta["base_url"],
                        "repaired_payload": repaired,
                    },
                )
                _write_json(output_dir / "technical_reasoning_parsed.json", repaired)
                return repaired
            _write_json(output_dir / "technical_reasoning_parsed.json", parsed)
            return parsed
        except json.JSONDecodeError:
            continue

    repaired, repaired_meta = _repair_json_with_llm(incident_id=incident_id, raw_text=raw_text)
    _write_json(
        output_dir / "technical_reasoning_repaired.json",
        {
            "incident_id": incident_id,
            "stage": "technical_reasoner_json_repair",
            "model": repaired_meta["model"],
            "provider_env": repaired_meta["api_key_env"],
            "base_url": repaired_meta["base_url"],
            "repaired_payload": repaired,
        },
    )
    _write_json(output_dir / "technical_reasoning_parsed.json", repaired)
    return repaired


def _load_external_enrichment(run_dir: Path) -> dict[str, Any]:
    """Load cached on-chain enrichment from disk if available.

    The cache file is produced offline by scripts/fetch_external_enrichment.py.
    We surface a normalized subset so downstream agents do not depend on the
    raw external-explorer schema.
    """
    cache_path = run_dir / "external_enrichment.json"
    if not cache_path.exists():
        return {"status": "unavailable", "reason": "cache_not_found"}
    try:
        raw = json.loads(cache_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"cache_read_error: {exc}"}

    endpoints = raw.get("endpoints", {}) or {}

    def _pick(short_name: str, field: str) -> list:
        for path, data in endpoints.items():
            if path.endswith(short_name) and isinstance(data, dict):
                value = data.get(field)
                if isinstance(value, list):
                    return value
        return []

    address_labels = _pick("address-label", "labels")
    balance_changes = _pick("balance-change", "balanceChanges")
    state_changes = _pick("state-change", "stateChanges")
    fund_transfers = _pick("fundflow", "transfers")

    if not any([address_labels, balance_changes, state_changes, fund_transfers]):
        return {"status": "empty", "reason": "no_endpoint_data"}

    return {
        "status": "loaded",
        "reason": "ok",
        "tx_hash": raw.get("tx_hash", ""),
        "address_labels": address_labels,
        "balance_changes": balance_changes,
        "state_changes": state_changes,
        "fund_transfers": fund_transfers,
    }


def _run_external_enrichment_stage(
    *,
    run_dir: Path,
    trace: TraceCollector,
) -> dict[str, Any]:
    with trace.record(
        "external_enrichment_loader",
        agent_type="rule",
        input_summary=f"run_dir={run_dir.name}",
    ) as slot:
        enrichment = _load_external_enrichment(run_dir)
        n_labels = len(enrichment.get("address_labels", []))
        n_bal = len(enrichment.get("balance_changes", []))
        n_state = len(enrichment.get("state_changes", []))
        n_tx = len(enrichment.get("fund_transfers", []))
        slot.output_summary = (
            f"{enrichment.get('status')}; "
            f"{n_labels} labels, {n_bal} balance_changes, "
            f"{n_state} state_changes, {n_tx} transfers"
        )
    return enrichment


def _run_external_validation_stage(
    *,
    seed: IncidentSeed,
    tx_hashes: list[str],
    transactions: list[dict[str, Any]],
    tx_root: Path,
    trace: TraceCollector,
) -> dict[str, Any]:
    # External-explorer validation is disabled in the public build. The pipeline
    # consumes any cached enrichment present under data/fixtures/runs/, but does
    # not perform live API calls.
    with trace.record(
        "external_validation",
        agent_type="rule",
        input_summary=f"{len(tx_hashes)} tx(s) on {seed.chain}",
    ) as slot:
        external_validation = {
            "status": "unavailable",
            "reason": "external_call_disabled",
            "chain": seed.chain,
            "tx_hashes": tx_hashes,
            "transactions": [],
        }
        slot.output_summary = "unavailable; external_call_disabled"
    return external_validation


def _run_planner_stage(
    *,
    seed: IncidentSeed,
    transactions: list[dict[str, Any]],
    run_dir: Path,
    trace: TraceCollector,
) -> dict[str, Any]:
    with trace.record(
        "planner",
        agent_type="rule",
        input_summary=f"{len(transactions)} transactions on {seed.chain}",
    ) as slot:
        try:
            analysis_plan = run_technical_planner(
                incident_id=seed.incident_id,
                chain=seed.chain,
                transactions=transactions,
                output_dir=run_dir,
            )
            roles = analysis_plan.get("roles", {})
            slot.output_summary = (
                f"{len(roles)} role categories; "
                f"{len(analysis_plan.get('priority_contracts', []))} priority contracts"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "technical.planner_failed",
                extra={"incident_id": seed.incident_id, "error": str(exc)},
            )
            analysis_plan = {"roles": {}, "priority_contracts": [], "newly_deployed": []}
            slot.output_summary = f"fallback (error: {exc})"
    return analysis_plan


def _run_contract_intelligence_stage(
    *,
    seed: IncidentSeed,
    rpc_url: str,
    analysis_plan: dict[str, Any],
    run_dir: Path,
    trace: TraceCollector,
) -> dict[str, Any]:
    with trace.record(
        "contract_intelligence",
        agent_type="rule",
        input_summary=f"{len(analysis_plan.get('priority_contracts', []))} priority contracts",
    ) as slot:
        try:
            contract_inventory = run_contract_intelligence(
                incident_id=seed.incident_id,
                chain=seed.chain,
                rpc_url=rpc_url,
                plan=analysis_plan,
                output_dir=run_dir,
            )
            slot.output_summary = (
                f"{len(contract_inventory.get('contracts', {}))} contracts in inventory"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "technical.contract_intelligence_failed",
                extra={"incident_id": seed.incident_id, "error": str(exc)},
            )
            contract_inventory = {"contracts": {}}
            slot.output_summary = f"fallback (error: {exc})"
    return contract_inventory


def _run_reasoner_and_revision_loop(
    *,
    seed: IncidentSeed,
    transactions: list[dict[str, Any]],
    source_context: dict[str, Any] | None,
    analysis_plan: dict[str, Any],
    contract_inventory: dict[str, Any],
    external_validation: dict[str, Any],
    tx_hashes: list[str],
    run_dir: Path,
    trace: TraceCollector,
    base_payload: dict[str, Any],
    initial_status: str,
) -> dict[str, Any]:
    reasoning = base_payload["reasoning"]
    revision_round = 0
    status = initial_status

    with trace.record(
        "technical_reasoner",
        agent_type="llm",
        input_summary=f"{len(transactions)} txs, {len(contract_inventory.get('contracts', {}))} contracts",
        notes="tokens: not captured (response parsed internally)",
    ) as slot_tr:
        try:
            reasoning = run_technical_reasoner(
                incident_id=seed.incident_id,
                seed=seed,
                transactions=transactions,
                source_context=source_context,
                output_dir=run_dir,
                analysis_plan=analysis_plan,
                contract_inventory=contract_inventory,
            )
            slot_tr.output_summary = (
                f"{len(reasoning.get('timeline_steps', []))} timeline steps; "
                f"mechanism: {str(reasoning.get('exploit_mechanism', ''))[:80]}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "technical.reasoning_fallback",
                extra={"incident_id": seed.incident_id, "error": str(exc)},
            )
            status = "partial" if status == "completed" else status
            reasoning = {
                "attack_flow_summary": "",
                "exploit_mechanism": "",
                "tx_role_map": {},
                "contract_role_map": {},
                "timeline_steps": [],
                "funds_flow_path": [],
                "open_questions": [f"Reasoning unavailable: {exc}"],
                "confidence_notes": ["Deterministic artifacts were collected without GLM reasoning."],
            }
            slot_tr.output_summary = f"fallback (error: {exc})"

    key_addresses = sorted(
        {
            address
            for item in transactions
            for address in item.get("summary", {}).get("addresses_seen", [])
            if address
        }
    )
    key_contracts = sorted(
        {
            address
            for item in transactions
            for address in item.get("summary", {}).get("contracts_touched", [])
            if address
        }
    )

    def build_payload(reasoning_block: dict[str, Any], round_index: int) -> dict[str, Any]:
        return {
            **base_payload,
            "transactions": transactions,
            "reasoning": reasoning_block,
            "analysis_plan": analysis_plan,
            "contract_inventory": contract_inventory,
            "external_validation": external_validation,
            "revision_round": round_index,
            "merge_back": {
                "summary": reasoning_block.get("attack_flow_summary", ""),
                "timeline_steps": reasoning_block.get("timeline_steps", []),
                "funds_flow_path": reasoning_block.get("funds_flow_path", []),
                "key_addresses": key_addresses,
                "key_contracts": key_contracts,
                "key_transactions": tx_hashes,
                "external_validation": external_validation,
                "open_questions": reasoning_block.get("open_questions", []),
            },
            "status": status,
        }

    payload = build_payload(reasoning, revision_round)
    with trace.record(
        "semantic_validator",
        agent_type="rule",
        input_summary=f"revision_round={revision_round}",
    ) as slot_sv:
        payload["validation"] = validate_technical_analysis(payload)
        verdict = payload["validation"].get("verdict", "")
        needs_rev = payload["validation"].get("needs_revision", False)
        slot_sv.output_summary = (
            f"severity={payload['validation'].get('severity', '?')}; "
            f"needs_revision={needs_rev}; verdict: {str(verdict)[:100]}"
        )

    if payload["validation"].get("needs_revision"):
        critique = payload["validation"].get("revision_request", "")
        trace.set_revision(critique)
        logger.info(
            "technical.reasoner_revision",
            extra={"incident_id": seed.incident_id, "critique_chars": len(critique)},
        )
        with trace.record(
            "technical_reasoner_revision",
            agent_type="llm",
            input_summary=f"revision critique ({len(critique)} chars)",
            notes="tokens: not captured (response parsed internally)",
        ) as slot_trr:
            try:
                revised_reasoning = run_technical_reasoner(
                    incident_id=seed.incident_id,
                    seed=seed,
                    transactions=transactions,
                    source_context=source_context,
                    output_dir=run_dir,
                    analysis_plan=analysis_plan,
                    contract_inventory=contract_inventory,
                    revision_critique=critique,
                )
                reasoning = revised_reasoning
                revision_round = 1
                payload = build_payload(reasoning, revision_round)
                with trace.record(
                    "semantic_validator_post_revision",
                    agent_type="rule",
                    input_summary="revision_round=1",
                ) as slot_sv2:
                    payload["validation"] = validate_technical_analysis(payload)
                    slot_sv2.output_summary = (
                        f"severity={payload['validation'].get('severity', '?')}; "
                        f"verdict: {str(payload['validation'].get('verdict', ''))[:100]}"
                    )
                slot_trr.output_summary = (
                    f"{len(reasoning.get('timeline_steps', []))} timeline steps after revision"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "technical.revision_failed",
                    extra={"incident_id": seed.incident_id, "error": str(exc)},
                )
                payload["revision_error"] = str(exc)
                slot_trr.output_summary = f"revision failed: {exc}"

    return payload


def run_incident_technical_analysis(
    *,
    seed: IncidentSeed,
    run_dir: Path,
    source_context: dict[str, Any] | None = None,
    trace: TraceCollector | None = None,
) -> dict[str, Any]:
    # If a caller-level TraceCollector is provided, instrument into it so all
    # records appear in one merged trace.  Otherwise create a local one for
    # backward compatibility (legacy / standalone callers).
    _owns_trace = trace is None
    if _owns_trace:
        trace = TraceCollector()
    artifact_path = run_dir / "technical_analysis.json"
    tx_hashes = [tx for tx in seed.attack_tx_hashes if tx]
    base_payload = {
        "incident_id": seed.incident_id,
        "chain": seed.chain,
        "generated_at": utc_now_iso(),
        "primary_tx_hash": tx_hashes[0] if tx_hashes else "",
        "tx_hashes": tx_hashes,
        "transactions": [],
        "analysis_plan": {"roles": {}, "priority_contracts": [], "newly_deployed": []},
        "contract_inventory": {"contracts": {}},
        "external_validation": {
            "status": "unavailable",
            "reason": "not_requested",
            "chain": seed.chain,
            "tx_hashes": tx_hashes,
            "transactions": [],
        },
        "external_enrichment": {"status": "unavailable", "reason": "not_loaded"},
        "revision_round": 0,
        "reasoning": {
            "attack_flow_summary": "",
            "exploit_mechanism": "",
            "tx_role_map": {},
            "contract_role_map": {},
            "timeline_steps": [],
            "funds_flow_path": [],
            "open_questions": [],
            "confidence_notes": [],
        },
        "validation": {},
        "merge_back": {
            "summary": "",
            "timeline_steps": [],
            "funds_flow_path": [],
            "key_addresses": [],
            "key_contracts": [],
            "key_transactions": tx_hashes,
            "open_questions": [],
        },
        "status": "skipped",
    }

    if not tx_hashes:
        payload = {
            **base_payload,
            "validation": {
                "verdict": "Technical analysis was skipped because the incident seed has no attack transaction hash.",
                "unresolved_gaps": ["attack_tx_hashes missing"],
                "checked_transactions": 0,
            },
        }
        _write_json(artifact_path, payload)
        return payload

    rpc_url = _rpc_url_for_chain(seed.chain)
    if not rpc_url:
        payload = {
            **base_payload,
            "validation": {
                "verdict": "Technical analysis was skipped because no configured RPC is available for this chain.",
                "unresolved_gaps": [f"Missing configured RPC for chain {seed.chain}."],
                "checked_transactions": 0,
            },
        }
        _write_json(artifact_path, payload)
        return payload

    tx_root = run_dir / "technical_analysis"
    tx_root.mkdir(parents=True, exist_ok=True)

    def collect_one(tx_hash: str) -> dict[str, Any]:
        return collect_transaction_artifacts(tx_hash, seed.chain, rpc_url, tx_root / tx_hash)

    with trace.record(
        "collector",
        agent_type="rule",
        input_summary=f"{len(tx_hashes)} tx(s): {', '.join(tx_hashes[:3])}",
    ) as _slot_collector:
        with ThreadPoolExecutor(max_workers=min(2, max(1, len(tx_hashes)))) as executor:
            transactions = list(executor.map(collect_one, tx_hashes))
        statuses_seen = {t.get("status", "unknown") for t in transactions}
        _slot_collector.output_summary = (
            f"{len(transactions)} artifact bundle(s) collected; statuses: {', '.join(sorted(statuses_seen))}"
        )

    statuses = {item.get("status", "") for item in transactions}
    status = "completed"
    if statuses & {"failed"} and statuses <= {"failed"}:
        status = "failed"
    elif statuses & {"partial", "failed"}:
        status = "partial"

    external_validation = _run_external_validation_stage(
        seed=seed,
        tx_hashes=tx_hashes,
        transactions=transactions,
        tx_root=tx_root,
        trace=trace,
    )

    external_enrichment = _run_external_enrichment_stage(
        run_dir=run_dir,
        trace=trace,
    )

    analysis_plan = _run_planner_stage(
        seed=seed,
        transactions=transactions,
        run_dir=run_dir,
        trace=trace,
    )

    contract_inventory = _run_contract_intelligence_stage(
        seed=seed,
        rpc_url=rpc_url,
        analysis_plan=analysis_plan,
        run_dir=run_dir,
        trace=trace,
    )

    payload = _run_reasoner_and_revision_loop(
        seed=seed,
        transactions=transactions,
        source_context=source_context,
        analysis_plan=analysis_plan,
        contract_inventory=contract_inventory,
        external_validation=external_validation,
        tx_hashes=tx_hashes,
        run_dir=run_dir,
        trace=trace,
        base_payload=base_payload,
        initial_status=status,
    )
    payload["external_enrichment"] = external_enrichment

    # Always embed the trace snapshot into technical_analysis.json (backward compat).
    # When trace is shared with the pipeline caller, this snapshot will only contain
    # the rule-based + technical-LLM records added so far; the pipeline-level LLM
    # records are appended later.  The final merged trace is written by pipeline.py
    # into augmented_incident.json after all stages complete.
    payload["pipeline_trace"] = trace.to_dict()
    _write_json(artifact_path, payload)
    # Only write the local pipeline_trace.md when we own the trace (standalone mode).
    # In merged mode pipeline.py owns the file write after all stages complete.
    if _owns_trace:
        (run_dir / "pipeline_trace.md").write_text(trace.to_markdown(), encoding="utf-8")
    return payload

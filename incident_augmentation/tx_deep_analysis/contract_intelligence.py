"""Contract-level intelligence for the technical-analysis stage.

For each priority contract from the `analysis_plan.json`:

- probe whether it is a proxy
  (EIP-1967 implementation slot, EIP-1167 minimal proxy bytecode)
- fetch its verified source + ABI from the chain's block explorer
  (Etherscan family) when available
- cache everything under
  `<run_dir>/technical_analysis/contracts/<addr>/{source.json, abi.json}`

Writes `<run_dir>/contract_inventory.json` as the aggregate output.

No LLM calls.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from incident_augmentation.models import utc_now_iso

from .collector import rpc_request

logger = logging.getLogger(__name__)

# EIP-1967 storage slots
_EIP1967_IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
_EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

# EIP-1167 minimal-proxy canonical bytecode. The 20-byte implementation
# address is embedded at offset 10..30 of the deployed code.
_MINIMAL_PROXY_PREFIX = "0x363d3d373d3d3d363d73"
_MINIMAL_PROXY_SUFFIX = "5af43d82803e903d91602b57fd5bf3"

# Etherscan V2 (2024) — one unified endpoint + one API key for 60+ chains via chainid param.
# Chain slug → (chain id used by V2 API, env var holding the unified Etherscan key).
# Per-chain legacy keys (BSCSCAN_API_KEY etc) are still consulted as fallback for backward compat.
_ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"
_CHAIN_EXPLORERS: dict[str, tuple[int, str]] = {
    "eth": (1, "ETHERSCAN_API_KEY"),
    "ethereum": (1, "ETHERSCAN_API_KEY"),
    "bsc": (56, "ETHERSCAN_API_KEY"),
    "bnb": (56, "ETHERSCAN_API_KEY"),
    "arb": (42161, "ETHERSCAN_API_KEY"),
    "arbitrum": (42161, "ETHERSCAN_API_KEY"),
    "base": (8453, "ETHERSCAN_API_KEY"),
    "opt": (10, "ETHERSCAN_API_KEY"),
    "optimism": (10, "ETHERSCAN_API_KEY"),
    "polygon": (137, "ETHERSCAN_API_KEY"),
    "avax": (43114, "ETHERSCAN_API_KEY"),
    "avalanche": (43114, "ETHERSCAN_API_KEY"),
}

_RATE_LIMIT_DELAY_SEC = 0.21  # ~4.7 req/sec, just under Etherscan's free-tier ceiling
_MAX_RETRIES = 3


def _explorer_for(chain: str) -> tuple[str, str] | None:
    return _CHAIN_EXPLORERS.get(str(chain or "").lower())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _is_zero_word(hex_str: str | None) -> bool:
    if not hex_str:
        return True
    return int(hex_str, 16) == 0


def _extract_address_from_slot(slot_value: str) -> str:
    # Slot is a 32-byte word; address is the trailing 20 bytes.
    cleaned = slot_value.lower().removeprefix("0x")
    if len(cleaned) < 40:
        return ""
    return "0x" + cleaned[-40:]


def _extract_minimal_proxy_target(code: str) -> str:
    cleaned = (code or "").lower()
    if not cleaned.startswith(_MINIMAL_PROXY_PREFIX):
        return ""
    if _MINIMAL_PROXY_SUFFIX not in cleaned:
        return ""
    # Bytes 10..30 of the deployed bytecode (positions 22..62 in the hex string
    # after the `0x` prefix).
    hex_body = cleaned[2:]
    impl = hex_body[20:60]
    if len(impl) != 40 or int(impl, 16) == 0:
        return ""
    return "0x" + impl


def detect_proxy(rpc_url: str, address: str) -> dict[str, Any]:
    """Probe an on-chain address for known proxy patterns.

    Returns a dict:
        {
          "is_proxy": bool,
          "proxy_type": "EIP-1967" | "minimal_proxy" | "",
          "implementation_address": "0x..." | "",
          "admin_address": "0x..." | "",
          "errors": [str, ...]
        }
    """
    errors: list[str] = []
    result = {
        "is_proxy": False,
        "proxy_type": "",
        "implementation_address": "",
        "admin_address": "",
        "errors": errors,
    }

    # EIP-1967 implementation slot.
    try:
        impl_slot_value = (
            rpc_request(rpc_url, "eth_getStorageAt", [address, _EIP1967_IMPL_SLOT, "latest"]).get("result")
            or "0x0"
        )
        if not _is_zero_word(impl_slot_value):
            result["is_proxy"] = True
            result["proxy_type"] = "EIP-1967"
            result["implementation_address"] = _extract_address_from_slot(impl_slot_value)
            # Optional: admin slot for debugging. Don't fail the whole probe on error.
            try:
                admin_slot_value = (
                    rpc_request(rpc_url, "eth_getStorageAt", [address, _EIP1967_ADMIN_SLOT, "latest"]).get("result")
                    or "0x0"
                )
                if not _is_zero_word(admin_slot_value):
                    result["admin_address"] = _extract_address_from_slot(admin_slot_value)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"admin slot read failed: {exc}")
            return result
    except Exception as exc:  # noqa: BLE001
        errors.append(f"EIP-1967 slot read failed: {exc}")

    # EIP-1167 minimal proxy pattern — walk eth_getCode.
    try:
        code_payload = rpc_request(rpc_url, "eth_getCode", [address, "latest"])
        code = code_payload.get("result") or ""
        target = _extract_minimal_proxy_target(code)
        if target:
            result["is_proxy"] = True
            result["proxy_type"] = "minimal_proxy"
            result["implementation_address"] = target
            return result
    except Exception as exc:  # noqa: BLE001
        errors.append(f"eth_getCode failed: {exc}")

    return result


def _etherscan_get_source(base_url: str, api_key: str, address: str, chainid: int = 1) -> dict[str, Any]:
    """Call `module=contract&action=getsourcecode` via Etherscan V2 multichain endpoint.

    `chainid` selects the target chain (1=ETH, 56=BSC, 42161=ARB, 8453=Base, 10=OP, 137=Polygon, 43114=AVAX).
    Returns raw API payload.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.get(
                base_url,
                params={
                    "chainid": chainid,
                    "module": "contract",
                    "action": "getsourcecode",
                    "address": address,
                    "apikey": api_key,
                },
                timeout=20,
            )
            if response.status_code == 429:
                raise RuntimeError("rate limited")
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            sleep_for = _RATE_LIMIT_DELAY_SEC * (2**attempt)
            time.sleep(sleep_for)
    raise RuntimeError(f"getsourcecode failed after {_MAX_RETRIES} attempts: {last_exc}")


def fetch_verified_source(
    *,
    chain: str,
    address: str,
    contracts_root: Path,
) -> dict[str, Any]:
    """Fetch verified source + ABI from the chain's explorer.

    Returns a dict with `classification`, `contract_name`, `compiler_version`,
    `source_path`, `abi_path`, `fetched_at`, `fetch_errors`.
    Always returns — never raises.
    """
    fetch_errors: list[str] = []
    explorer = _explorer_for(chain)
    if not explorer:
        fetch_errors.append(f"no explorer configured for chain '{chain}'")
        return {
            "classification": "failed",
            "contract_name": "",
            "compiler_version": "",
            "source_path": "",
            "abi_path": "",
            "fetched_at": utc_now_iso(),
            "fetch_errors": fetch_errors,
        }

    chainid, env_key = explorer
    base_url = _ETHERSCAN_V2_URL
    api_key = os.environ.get(env_key, "")
    if not api_key:
        fetch_errors.append(f"no API key in env var {env_key}")

    contract_dir = contracts_root / address.lower()
    source_path = contract_dir / "source.json"
    abi_path = contract_dir / "abi.json"

    # Short-circuit on cache hit.
    cached = _read_json(source_path)
    if cached:
        result_block = (cached.get("result") or [{}])[0]
        source_code = result_block.get("SourceCode", "")
        classification = "verified" if source_code else "unverified"
        return {
            "classification": classification,
            "contract_name": result_block.get("ContractName", ""),
            "compiler_version": result_block.get("CompilerVersion", ""),
            "source_path": str(source_path),
            "abi_path": str(abi_path) if abi_path.exists() else "",
            "fetched_at": utc_now_iso(),
            "fetch_errors": fetch_errors,
            "cache_hit": True,
        }

    if not api_key:
        return {
            "classification": "failed",
            "contract_name": "",
            "compiler_version": "",
            "source_path": "",
            "abi_path": "",
            "fetched_at": utc_now_iso(),
            "fetch_errors": fetch_errors,
        }

    try:
        payload = _etherscan_get_source(base_url, api_key, address, chainid=chainid)
    except Exception as exc:  # noqa: BLE001
        fetch_errors.append(str(exc))
        return {
            "classification": "failed",
            "contract_name": "",
            "compiler_version": "",
            "source_path": "",
            "abi_path": "",
            "fetched_at": utc_now_iso(),
            "fetch_errors": fetch_errors,
        }

    _write_json(source_path, payload)
    result_block = (payload.get("result") or [{}])[0]
    source_code = result_block.get("SourceCode", "")
    abi_str = result_block.get("ABI", "")
    if abi_str and abi_str not in ("", "Contract source code not verified"):
        try:
            _write_json(abi_path, json.loads(abi_str))
        except json.JSONDecodeError:
            fetch_errors.append("ABI field could not be parsed as JSON")

    classification = "verified" if source_code else "unverified"
    return {
        "classification": classification,
        "contract_name": result_block.get("ContractName", ""),
        "compiler_version": result_block.get("CompilerVersion", ""),
        "source_path": str(source_path),
        "abi_path": str(abi_path) if abi_path.exists() else "",
        "fetched_at": utc_now_iso(),
        "fetch_errors": fetch_errors,
    }


def run_contract_intelligence(
    *,
    incident_id: str,
    chain: str,
    rpc_url: str,
    plan: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Build `contract_inventory.json` from the planner's priority list."""
    contracts_root = output_dir / "technical_analysis" / "contracts"
    contracts_root.mkdir(parents=True, exist_ok=True)

    # Addresses we care about: planner's priority_contracts + newly_deployed.
    address_roles: dict[str, str] = {}
    for entry in plan.get("priority_contracts", []) or []:
        addr = str(entry.get("address") or "").lower()
        if addr and addr not in address_roles:
            address_roles[addr] = entry.get("role", "")
    for entry in plan.get("newly_deployed", []) or []:
        addr = str(entry.get("address") or "").lower()
        if addr and addr not in address_roles:
            address_roles[addr] = "attacker_contract"

    newly_deployed_lookup = {
        str(entry.get("address") or "").lower(): entry
        for entry in plan.get("newly_deployed", []) or []
    }

    contracts: dict[str, Any] = {}
    for address, role in address_roles.items():
        # Newly deployed contracts don't exist on "latest" (they were
        # destroyed or sit at the post-tx state). Skip RPC probes and source
        # fetch for them — mark as unverified + newly_deployed.
        if address in newly_deployed_lookup:
            deployment = newly_deployed_lookup[address]
            contracts[address] = {
                "address": address,
                "role": role or "attacker_contract",
                "classification": "unverified",
                "is_proxy": False,
                "proxy_type": "",
                "implementation_address": "",
                "implementation_classification": "",
                "contract_name": "",
                "compiler_version": "",
                "source_path": "",
                "abi_path": "",
                "newly_deployed_in_tx": deployment.get("tx_hash", ""),
                "create_type": deployment.get("create_type", ""),
                "fetched_at": utc_now_iso(),
                "fetch_errors": ["newly deployed in-tx — no on-chain source"],
            }
            continue

        proxy_info = detect_proxy(rpc_url, address) if rpc_url else {
            "is_proxy": False, "proxy_type": "", "implementation_address": "", "admin_address": "",
            "errors": ["no RPC URL configured"],
        }
        source_info = fetch_verified_source(chain=chain, address=address, contracts_root=contracts_root)

        implementation_address = proxy_info.get("implementation_address", "")
        implementation_classification = ""
        if implementation_address:
            impl_source = fetch_verified_source(
                chain=chain,
                address=implementation_address,
                contracts_root=contracts_root,
            )
            implementation_classification = impl_source.get("classification", "")

        contracts[address] = {
            "address": address,
            "role": role,
            "classification": source_info.get("classification", ""),
            "is_proxy": proxy_info.get("is_proxy", False),
            "proxy_type": proxy_info.get("proxy_type", ""),
            "implementation_address": implementation_address,
            "implementation_classification": implementation_classification,
            "admin_address": proxy_info.get("admin_address", ""),
            "contract_name": source_info.get("contract_name", ""),
            "compiler_version": source_info.get("compiler_version", ""),
            "source_path": source_info.get("source_path", ""),
            "abi_path": source_info.get("abi_path", ""),
            "fetched_at": source_info.get("fetched_at", ""),
            "fetch_errors": (source_info.get("fetch_errors") or []) + proxy_info.get("errors", []),
        }

        # Be polite to the explorer.
        time.sleep(_RATE_LIMIT_DELAY_SEC)

    inventory = {
        "incident_id": incident_id,
        "chain": chain,
        "generated_at": utc_now_iso(),
        "contracts": contracts,
    }
    _write_json(output_dir / "contract_inventory.json", inventory)
    logger.info(
        "technical.contract_intelligence_done",
        extra={"incident_id": incident_id, "contracts": len(contracts)},
    )
    return inventory

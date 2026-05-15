from __future__ import annotations

from typing import Any

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# selector → human-readable signature. Kept lowercase 0x… form.
# Grouped by semantic category so the planner can classify addresses without
# pattern-matching on labels.
KNOWN_SELECTORS: dict[str, str] = {
    # ERC-20
    "0xa9059cbb": "transfer(address,uint256)",
    "0x095ea7b3": "approve(address,uint256)",
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0x40c10f19": "mint(address,uint256)",
    "0x42966c68": "burn(uint256)",
    "0x70a08231": "balanceOf(address)",
    # WETH / vault
    "0xd0e30db0": "deposit()",
    "0x2e1a7d4d": "withdraw(uint256)",
    # Uniswap-V2-style router
    "0x38ed1739": "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
    "0x8803dbee": "swapTokensForExactTokens(uint256,uint256,address[],address,uint256)",
    "0x18cbafe5": "swapExactETHForTokens(uint256,address[],address,uint256)",
    "0x7ff36ab5": "swapExactETHForTokensSupportingFeeOnTransferTokens(uint256,address[],address,uint256)",
    "0x4a25d94a": "swapTokensForExactETH(uint256,uint256,address[],address,uint256)",
    "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens(uint256,uint256,address[],address,uint256)",
    # Uniswap-V2 pair
    "0x022c0d9f": "swap(uint256,uint256,address,bytes)",
    # Flash loan / callback
    "0xab9c4b5d": "flashLoan(address,address[],uint256[],uint256[],address,bytes,uint16)",
    "0x5cffe9de": "flashLoan(address,uint256,bytes)",
    "0x490e6cbc": "flashBorrow(address,uint256,bytes)",
    "0x10d1e85c": "uniswapV2Call(address,uint256,uint256,bytes)",
    "0xfa461e33": "uniswapV3SwapCallback(int256,int256,bytes)",
    "0xe9cbafb0": "uniswapV3FlashCallback(uint256,uint256,bytes)",
    "0x920f5c84": "executeOperation(address[],uint256[],uint256[],address,bytes)",
    # Oracles
    "0x50d25bcd": "latestAnswer()",
    "0xfeaf968c": "latestRoundData()",
    "0x0902f1ac": "getReserves()",
}

# Semantic category per selector. Used by the planner to label roles from trace
# evidence alone (no LLM involved).
SELECTOR_CATEGORIES: dict[str, str] = {
    "0xa9059cbb": "transfer",
    "0x23b872dd": "transfer",
    "0x095ea7b3": "approve",
    "0x40c10f19": "mint",
    "0xd0e30db0": "mint",
    "0x42966c68": "burn",
    "0x2e1a7d4d": "burn",
    "0x38ed1739": "swap",
    "0x8803dbee": "swap",
    "0x18cbafe5": "swap",
    "0x7ff36ab5": "swap",
    "0x4a25d94a": "swap",
    "0x791ac947": "swap",
    "0x022c0d9f": "swap",
    "0xab9c4b5d": "flashloan",
    "0x5cffe9de": "flashloan",
    "0x490e6cbc": "flashloan",
    "0x10d1e85c": "flashloan",
    "0xfa461e33": "flashloan",
    "0xe9cbafb0": "flashloan",
    "0x920f5c84": "flashloan",
    "0x50d25bcd": "oracle",
    "0xfeaf968c": "oracle",
    "0x0902f1ac": "oracle",
    "0x70a08231": "read",
}

CREATE_TYPES = {"CREATE", "CREATE2"}


def _hex_to_int(value: str | None) -> int:
    raw = str(value or "0x0")
    try:
        return int(raw, 16)
    except ValueError:
        return 0


def _short_selector_name(selector: str) -> str:
    return KNOWN_SELECTORS.get(selector, "unknown_selector")


def _selector_category(selector: str) -> str:
    if not selector:
        return ""
    return SELECTOR_CATEGORIES.get(selector, "other")


def _trace_root(trace_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trace_payload:
        return None
    root = trace_payload.get("result") or trace_payload
    return root if isinstance(root, dict) else None


def decode_trace_calls(trace_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Flatten a callTracer trace into an ordered list of call nodes."""
    root = _trace_root(trace_payload)
    if root is None:
        return []

    flattened: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], depth: int, path: str) -> None:
        input_data = str(node.get("input") or "0x")
        selector = input_data[:10] if len(input_data) >= 10 else ""
        flattened.append(
            {
                "path": path,
                "depth": depth,
                "type": node.get("type", "CALL"),
                "from": node.get("from", ""),
                "to": node.get("to", ""),
                "value": _hex_to_int(node.get("value")),
                "selector": selector,
                "selector_label": _short_selector_name(selector) if selector else "",
                "selector_category": _selector_category(selector),
                "gas_used": _hex_to_int(node.get("gasUsed")),
                "error": node.get("error", ""),
            }
        )
        for index, child in enumerate(node.get("calls") or []):
            walk(child, depth + 1, f"{path}.{index}")

    walk(root, 0, "0")
    return flattened


def detect_created_contracts(trace_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return every CREATE / CREATE2 node in a trace.

    For each record:
        - address: the newly-deployed contract address (trace node's `to`
          field, per geth's callTracer semantics)
        - deployed_by: the parent `from`
        - create_type: "CREATE" | "CREATE2"
        - trace_path: dotted index path into the call tree
        - depth: tree depth
    """
    root = _trace_root(trace_payload)
    if root is None:
        return []

    deployments: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], depth: int, path: str) -> None:
        node_type = str(node.get("type", "")).upper()
        if node_type in CREATE_TYPES:
            address = str(node.get("to") or "").lower()
            if address:
                deployments.append(
                    {
                        "address": address,
                        "deployed_by": str(node.get("from") or "").lower(),
                        "create_type": node_type,
                        "trace_path": path,
                        "depth": depth,
                    }
                )
        for index, child in enumerate(node.get("calls") or []):
            walk(child, depth + 1, f"{path}.{index}")

    walk(root, 0, "0")
    return deployments


def summarize_funds_flow(tx_payload: dict[str, Any] | None, receipt_payload: dict[str, Any] | None) -> dict[str, Any]:
    tx = tx_payload or {}
    receipt = receipt_payload or {}
    native_transfers: list[dict[str, Any]] = []
    token_transfers: list[dict[str, Any]] = []

    value = _hex_to_int(tx.get("value"))
    if value > 0:
        native_transfers.append(
            {
                "from": tx.get("from", ""),
                "to": tx.get("to", ""),
                "value": value,
                "asset": "native",
            }
        )

    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if not topics or str(topics[0]).lower() != TRANSFER_TOPIC:
            continue
        from_addr = "0x" + str(topics[1])[-40:] if len(topics) > 1 else ""
        to_addr = "0x" + str(topics[2])[-40:] if len(topics) > 2 else ""
        token_transfers.append(
            {
                "token": log.get("address", ""),
                "from": from_addr,
                "to": to_addr,
                "value": _hex_to_int(log.get("data")),
            }
        )

    return {
        "native_transfers": native_transfers,
        "token_transfers": token_transfers,
        "summary": {
            "native_value_transfers": len(native_transfers),
            "token_transfers": len(token_transfers),
        },
    }

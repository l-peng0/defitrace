from __future__ import annotations

from collections import Counter
from typing import Any


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _clip(text: str, limit: int = 280) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _source_lookup(source_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("source_id", ""): item for item in source_index.get("sources", [])}


def _find_source(source_index: dict[str, Any], url: str) -> dict[str, Any] | None:
    for item in source_index.get("sources", []):
        if item.get("url") == url:
            return item
    return None


def _build_support_entry(source: dict[str, Any], note: str) -> dict[str, Any]:
    return {
        "source_id": source.get("source_id", ""),
        "url": source.get("url", ""),
        "source_type": source.get("source_type", "report"),
        "depth": source.get("depth", 0),
        "discovered_from": source.get("discovered_from", ""),
        "fetch_status": source.get("fetch_status", "unknown"),
        "note": note,
    }


def _claim_from_source(
    claim_id: str,
    title: str,
    statement: str,
    confidence: float,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "title": title,
        "statement": statement,
        "confidence": confidence,
        "support": sources,
    }


def _filter_public_sources(source_index: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_index.get("sources", []):
        url = str(source.get("url", ""))
        if not url or url in seen:
            continue
        lower = url.lower()
        if any(
            marker in lower
            for marker in [
                "/tree/main",
                "/tree/main/src",
                "/tree/main/src/test",
                "twitter.com/intent/",
                "t.me/share/",
                "/blog?tab=",
                "/settings",
                "/gastracker",
                "/chart/",
            ]
        ):
            continue
        seen.add(url)
        filtered.append(source)
    return filtered


def _build_generic_report(
    incident_id: str,
    augmented_incident: dict[str, Any],
    source_index: dict[str, Any],
    quality_report: dict[str, Any],
    technical_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an analyst report populated from all available pipeline output.

    The structure mirrors the schema used by the frontend:
    case_overview / attacker_profile / exploit_path / evidence_chain / open_questions.
    Every section falls back to short honest sentences rather than empty values so
    the report always renders something — even for a thin BGM-style run.
    """
    public_sources = _filter_public_sources(source_index)
    source_count = len(public_sources)
    source_types = Counter(source.get("source_type", "report") for source in public_sources)

    # ── Narrative from LLM stage (if available) ──────────────────────────────
    narrative: dict[str, Any] = augmented_incident.get("narrative") or {}
    executive_summary: str = (
        narrative.get("executive_summary")
        or augmented_incident.get("summary")
        or ""
    )
    attack_narrative: str = narrative.get("attack_narrative") or ""
    attacker_motive: str = narrative.get("attacker_motive") or ""
    key_takeaway: str = narrative.get("key_takeaway") or ""

    # ── Timeline steps ────────────────────────────────────────────────────────
    timeline: list[dict[str, Any]] = augmented_incident.get("timeline") or []

    # ── Attacker profile ──────────────────────────────────────────────────────
    attacker_profile_data: dict[str, Any] = augmented_incident.get("attacker_profile") or {}
    key_addresses: list[str] = augmented_incident.get("key_addresses") or []
    key_transactions: list[str] = augmented_incident.get("key_transactions") or []

    # ── Pattern hypotheses ────────────────────────────────────────────────────
    pattern_hypotheses: list[dict[str, Any]] = augmented_incident.get("pattern_hypotheses") or []
    pattern_summary: str = pattern_hypotheses[0].get("summary") if pattern_hypotheses else ""
    open_questions_from_pattern: list[str] = pattern_hypotheses[0].get("open_questions") if pattern_hypotheses else []

    # ── Technical analysis merge-back ─────────────────────────────────────────
    technical_merge: dict[str, Any] = (technical_analysis or {}).get("merge_back") or {}
    exploit_mechanism: str = (technical_analysis or {}).get("reasoning", {}).get("exploit_mechanism") or ""

    # ── Quality report ────────────────────────────────────────────────────────
    completeness_score: float = quality_report.get("completeness_score") or 0.0
    judge_summary: str = quality_report.get("judge_summary") or ""
    missing_fields: list[str] = quality_report.get("missing_fields") or []

    # ─────────────────────────────────────────────────────────────────────────
    # case_overview
    # ─────────────────────────────────────────────────────────────────────────
    what_happened = (
        executive_summary
        or f"The {augmented_incident.get('title') or incident_id} case was rebuilt from seed links, fetched source pages, and second-hop source expansion."
    )
    why_it_matters = (
        key_takeaway
        or judge_summary
        or (
            f"This case is supported by {source_count} source(s) across {len(source_types)} source type(s). "
            "Stronger technical confirmation is still needed before this should be treated as analyst-grade."
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # attacker_profile
    # ─────────────────────────────────────────────────────────────────────────
    attacker_summary = (
        attacker_motive
        or attacker_profile_data.get("recent_activity_summary")
        or (
            f"The current dossier has {len(key_addresses)} address candidate(s). "
            "No strong entity cluster has been confirmed yet."
        )
    )
    behavior_signals: list[str] = attacker_profile_data.get("repeated_behaviors") or []
    if not behavior_signals and pattern_summary:
        behavior_signals = [pattern_summary]
    if not behavior_signals:
        behavior_signals = ["No repeated behavior pattern confirmed yet — more source evidence is needed."]

    # ─────────────────────────────────────────────────────────────────────────
    # exploit_path (steps)
    # ─────────────────────────────────────────────────────────────────────────
    exploit_path_summary = (
        attack_narrative
        or exploit_mechanism
        or executive_summary
        or f"The exploit path for {incident_id} still needs stronger reconstruction."
    )
    if timeline:
        exploit_steps = [
            {
                "title": step.get("label") or step.get("title") or f"Step {idx + 1}",
                "detail": (
                    step.get("summary")
                    or step.get("description")
                    or step.get("action")
                    or step.get("detail")
                    or ""
                ),
                "evidence_refs": step.get("source_refs") or step.get("evidence_refs") or [],
                "tx_hashes": step.get("tx_hashes") or [],
                "timestamp": step.get("timestamp") or "",
                "chain": step.get("chain") or augmented_incident.get("chain") or "",
                "called_contracts": step.get("called_contracts") or [],
                "function_selectors": step.get("function_selectors") or [],
                "verification_status": step.get("verification_status") or "partial",
            }
            for idx, step in enumerate(timeline[:6])
        ]
    else:
        exploit_steps = [
            {
                "title": "Exploit path not yet reconstructed",
                "detail": (
                    f"No timeline could be reconstructed — the run had {source_count} source document(s) "
                    "and no full tx trace was available."
                ),
                "evidence_refs": [],
                "tx_hashes": [],
                "timestamp": "",
                "chain": augmented_incident.get("chain") or "",
                "called_contracts": [],
                "function_selectors": [],
                "verification_status": "not_confirmed",
            }
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # evidence_chain
    # ─────────────────────────────────────────────────────────────────────────
    if technical_analysis:
        evidence_summary = (
            "The current case file combines public sources with a stored technical-analysis artifact. "
            f"Technical validation verdict: {(technical_analysis or {}).get('validation', {}).get('verdict', 'pending')}."
        )
    else:
        evidence_summary = (
            f"The current case file keeps {source_count} public source(s) across {len(source_types)} source type(s). "
            "A deeper technical pass is still needed."
        )

    evidence_claims = [
        _claim_from_source(
            "claim-overview",
            "Current public summary",
            executive_summary or f"The case {incident_id} still depends on an incomplete public summary.",
            0.58,
            [
                _build_support_entry(source, "Supports the current public-facing summary.")
                for source in public_sources[:3]
            ],
        )
    ]
    if attack_narrative:
        evidence_claims.append(
            _claim_from_source(
                "claim-attack-narrative",
                "LLM-synthesised attack narrative",
                _clip(attack_narrative, 300),
                0.65,
                [],
            )
        )
    if exploit_mechanism:
        evidence_claims.append(
            _claim_from_source(
                "claim-exploit-mechanism",
                "Technical exploit mechanism",
                _clip(exploit_mechanism, 300),
                0.70,
                [],
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # open_questions
    # ─────────────────────────────────────────────────────────────────────────
    open_questions: list[str] = []
    open_questions.extend(technical_merge.get("open_questions") or [])
    open_questions.extend(open_questions_from_pattern or [])
    open_questions.extend(missing_fields[:3])
    if not open_questions:
        open_questions = [
            "Which specific pricing path or oracle was abused first?",
            "Which address funded the exploit wallet immediately before the attack?",
            "Is there a direct explorer or postmortem source that confirms the exploit mechanism?",
            "Which bridge, exchange, or swap venue would have been the most likely exit route?",
        ]
    # deduplicate while preserving order
    open_questions = _unique(open_questions)

    # ─────────────────────────────────────────────────────────────────────────
    # fund_flow
    # ─────────────────────────────────────────────────────────────────────────
    technical_txs = technical_merge.get("key_transactions") or key_transactions
    technical_addrs = technical_merge.get("key_addresses") or key_addresses
    funds_flow_path = technical_merge.get("funds_flow_path") or []
    if funds_flow_path:
        fund_flow_summary = (
            f"Technical analysis traced transaction-level fund movement across {len(funds_flow_path)} step(s)."
        )
    elif key_transactions:
        fund_flow_summary = (
            f"The current public view has {len(key_transactions)} known transaction(s). "
            "A deeper fund-flow pass is still needed."
        )
    else:
        fund_flow_summary = (
            "The current public view only has a lightweight on-chain summary. "
            "A deeper fund-flow pass is still needed."
        )

    return {
        "incident_id": incident_id,
        "report_type": "analyst_report",
        "case_overview": {
            "headline": augmented_incident.get("title") or incident_id,
            "what_happened": what_happened,
            "why_it_matters": why_it_matters,
            "primary_sources": [
                _build_support_entry(source, "Primary source collected for the public case file.")
                for source in public_sources[:4]
            ],
        },
        "attacker_profile": {
            "summary": attacker_summary,
            "attacker_addresses": key_addresses[:8],
            "behavior_signals": behavior_signals,
            "primary_addresses": attacker_profile_data.get("primary_addresses") or key_addresses[:8],
            "related_address_count": attacker_profile_data.get("related_address_count", len(attacker_profile_data.get("related_addresses") or [])),
            "funding_source": attacker_profile_data.get("funding_source") or "Not confirmed",
            "deployment_to_attack_time": attacker_profile_data.get("deployment_to_attack_time") or "Not confirmed",
            "pre_attack_activity": attacker_profile_data.get("pre_attack_activity") or "Not confirmed",
            "post_attack_fund_flow": attacker_profile_data.get("post_attack_fund_flow") or "Not confirmed",
            "evidence_refs": attacker_profile_data.get("evidence_refs") or [],
            "confidence": attacker_profile_data.get("confidence") or "low",
        },
        "fund_flow": {
            "summary": fund_flow_summary,
            "key_transactions": technical_txs[:6],
            "key_addresses": technical_addrs[:8],
            "path": funds_flow_path,
        },
        "exploit_path": {
            "summary": exploit_path_summary,
            "steps": exploit_steps,
        },
        "evidence_chain": {
            "summary": evidence_summary,
            "claims": evidence_claims,
            "sources": public_sources,
        },
        "open_questions": open_questions,
    }


def build_analyst_report(
    *,
    incident_id: str,
    augmented_incident: dict[str, Any],
    source_index: dict[str, Any],
    quality_report: dict[str, Any],
    technical_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an analyst report for any incident through a single unified path.

    The Paribus-specific hardcode has been removed; all incidents are treated
    equally and populated from the fields already present in augmented_incident.
    """
    return _build_generic_report(
        incident_id, augmented_incident, source_index, quality_report, technical_analysis
    )

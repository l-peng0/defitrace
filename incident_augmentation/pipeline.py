from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor as _LLMExecutor
from pathlib import Path
from typing import Any

from .agent_trace import TraceCollector
from .analyst_report import build_analyst_report
from .llm_stages import (
    run_llm_evidence_extractor,
    run_llm_narrative_writer,
    run_llm_quality_assessor,
    run_llm_timeline_synthesizer,
)
from .models import IncidentSeed, RunState, utc_now_iso
from .source_expansion import (
    classify_url,
    extract_additional_urls,
    fetch_source_document,
    normalize_url,
)
from .tx_deep_analysis import run_incident_technical_analysis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# QA Retry configuration
# ---------------------------------------------------------------------------
# If the Quality Assessor returns a completeness_score below this threshold
# (or flags missing_dimensions), a single retry pass re-runs Evidence Extractor
# → Timeline Synthesizer → Narrative Writer → Quality Assessor with the QA
# critique injected into the Evidence prompt.  One-shot only — no further loops.
QA_RETRY_SCORE_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Confidence scores for raw evidence items built from the incident seed
# ---------------------------------------------------------------------------
CONFIDENCE_INCIDENT_NAME = 0.98
CONFIDENCE_PROTOCOL_NAME = 0.95
CONFIDENCE_INCIDENT_DATE = 0.92
CONFIDENCE_ATTACK_TX_HASH = 0.9
CONFIDENCE_ATTACKER_ADDRESS = 0.85
CONFIDENCE_SOURCE_TITLE_FETCHED = 0.8
CONFIDENCE_SOURCE_TITLE_UNFETCHED = 0.4
CONFIDENCE_ATTACK_TYPE_CANDIDATE = 0.7
CONFIDENCE_SUMMARY_CANDIDATE = 0.65
CONFIDENCE_MENTIONED_TX = 0.55
CONFIDENCE_MENTIONED_ADDRESS = 0.52

SCAN_HOSTS = {
    "ethereum": "https://etherscan.io",
    "eth": "https://etherscan.io",
    "bsc": "https://bscscan.com",
    "binance smart chain": "https://bscscan.com",
    "arbitrum": "https://arbiscan.io",
    "base": "https://basescan.org",
    "optimism": "https://optimistic.etherscan.io",
    "polygon": "https://polygonscan.com",
    "avalanche": "https://snowtrace.io",
    "blast": "https://blastscan.io",
}

AGENTS = {
    "source_finder": "Discovery supervisor",
    "source_expander": "Source expansion agent",
    "evidence_normalizer": "Evidence normalization agent",
    "timeline_builder": "Timeline builder agent",
    "attacker_profiler": "Attacker profiler agent",
    "pattern_reasoner": "Pattern reasoner agent",
    "dossier_assembler": "Dossier composer agent",
    "quality_judge": "QA judge agent",
    "dashboard_projection": "Projection agent",
}


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "incident"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _scan_base(chain: str) -> str:
    return SCAN_HOSTS.get(chain.lower(), "https://etherscan.io")


def _best_incident_date(seed: IncidentSeed) -> str:
    if seed.incident_date:
        return seed.incident_date
    if seed.date_range.get("first_seen"):
        return str(seed.date_range["first_seen"])
    return ""


def _build_incident_id(seed: IncidentSeed) -> str:
    name_basis = seed.incident_name or seed.protocol_name or seed.seed_type or "incident"
    parts = [name_basis, seed.chain, _best_incident_date(seed)]
    slug = _slugify("-".join(part for part in parts if part))
    return slug or "incident"


def load_seed(seed_path: str | Path) -> IncidentSeed:
    payload = json.loads(Path(seed_path).read_text())
    seed = IncidentSeed.from_dict(payload)
    seed.incident_id = _build_incident_id(seed)
    if not seed.job_id:
        seed.job_id = f"{seed.incident_id}-job"
    return seed


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def normalize_completeness_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return round(score, 2)


def build_source_index(seed: IncidentSeed) -> dict[str, Any]:
    scan_base = _scan_base(seed.chain)
    sources: list[dict[str, Any]] = []
    seen_normalized: set[str] = set()

    def add_source(url: str, source_type: str, discovered_from: str, depth: int, priority: int) -> None:
        if not url:
            return
        key = normalize_url(url)
        if key in seen_normalized:
            return
        seen_normalized.add(key)
        sources.append(
            {
                "source_id": f"src-{len(sources) + 1:03d}",
                "url": url,
                "source_type": source_type,
                "discovered_from": discovered_from,
                "depth": depth,
                "priority": priority,
                "fetch_status": "queued",
            }
        )

    def add_batch(
        values: list[str],
        discovered_from: str,
        base_priority: int,
        *,
        url_for: Any = lambda v: v,
        source_type: str | None = None,
    ) -> None:
        for index, value in enumerate(_unique(values), start=1):
            url = url_for(value)
            stype = source_type if source_type is not None else classify_url(url)
            add_source(url, stype, discovered_from, 0, base_priority - index)

    add_batch(seed.seed_urls, "incident_seed", 100)
    add_batch(
        seed.attack_tx_hashes,
        "attack_tx_hashes",
        80,
        url_for=lambda tx: f"{scan_base}/tx/{tx}",
        source_type="explorer",
    )
    add_batch(
        seed.attacker_addresses,
        "attacker_addresses",
        70,
        url_for=lambda addr: f"{scan_base}/address/{addr}",
        source_type="explorer",
    )
    add_batch(seed.attack_contract_urls, "attack_contract_urls", 60, source_type="explorer")
    add_batch(seed.victim_contract_urls, "victim_contract_urls", 50, source_type="explorer")

    return {"incident_id": seed.incident_id, "sources": sources}


def expand_sources(source_index: dict[str, Any], max_depth: int = 2) -> tuple[dict[str, Any], dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    working_sources = list(source_index["sources"])
    seen_urls = {item["url"] for item in working_sources if item.get("url")}
    fetched_source_ids: set[str] = set()

    for depth in range(0, max_depth + 1):
        pending_sources = [
            source
            for source in working_sources
            if source.get("depth", 0) == depth and source.get("source_id") not in fetched_source_ids
        ]
        if not pending_sources:
            continue

        with ThreadPoolExecutor(max_workers=min(6, max(1, len(pending_sources)))) as executor:
            fetched_documents = list(
                executor.map(
                    lambda source: fetch_source_document(
                        source_id=source["source_id"],
                        url=source["url"],
                        source_type=source["source_type"],
                    ),
                    pending_sources,
                )
            )

        for source, document in zip(pending_sources, fetched_documents, strict=False):
            fetched_source_ids.add(source["source_id"])
            documents.append(document.to_dict())
            source["fetch_status"] = document.fetch_status
            if depth >= max_depth:
                continue
            for link in document.discovered_links:
                if link["url"] in seen_urls:
                    continue
                seen_urls.add(link["url"])
                working_sources.append(
                    {
                        "source_id": f"src-{len(working_sources) + 1:03d}",
                        "url": link["url"],
                        "source_type": link["source_type"],
                        "discovered_from": document.source_id,
                        "depth": depth + 1,
                        "priority": max(10, 30 - (depth * 5)),
                        "fetch_status": "discovered",
                    }
                )

    return (
        {"incident_id": source_index["incident_id"], "sources": working_sources},
        {"incident_id": source_index["incident_id"], "documents": documents},
    )


def build_raw_evidence(seed: IncidentSeed, source_index: dict[str, Any], source_documents: dict[str, Any]) -> dict[str, Any]:
    evidence_items: list[dict[str, Any]] = []
    source_by_url = {item["url"]: item for item in source_index["sources"]}

    def append_item(
        fact_type: str,
        fact_value: str,
        fact_text: str,
        source_url: str,
        confidence: float,
        inferred: bool = False,
    ) -> None:
        source = source_by_url.get(source_url, {})
        evidence_items.append(
            {
                "evidence_id": f"ev-{len(evidence_items) + 1:03d}",
                "fact_type": fact_type,
                "fact_value": fact_value,
                "fact_text": fact_text,
                "source_url": source_url,
                "source_ref": source.get("source_id", ""),
                "source_type": source.get("source_type", "unknown"),
                "confidence": confidence,
                "is_inferred": inferred,
            }
        )

    seed_source = seed.seed_urls[0] if seed.seed_urls else "incident_seed.json"
    scan_base = _scan_base(seed.chain)
    if seed.incident_name:
        append_item("incident_name", seed.incident_name, f"Incident is named {seed.incident_name}.", seed_source, CONFIDENCE_INCIDENT_NAME)
    if seed.protocol_name:
        append_item("protocol_name", seed.protocol_name, f"Protocol appears to be {seed.protocol_name}.", seed_source, CONFIDENCE_PROTOCOL_NAME)
    if seed.incident_date:
        append_item("incident_date", seed.incident_date, f"Incident date is {seed.incident_date}.", seed_source, CONFIDENCE_INCIDENT_DATE)
    for value in _unique(seed.attack_tx_hashes):
        append_item("attack_transaction", value, f"Attack transaction hash observed: {value}.", f"{scan_base}/tx/{value}", CONFIDENCE_ATTACK_TX_HASH)
    for value in _unique(seed.attacker_addresses):
        append_item("attacker_address", value, f"Attacker-linked address observed: {value}.", f"{scan_base}/address/{value}", CONFIDENCE_ATTACKER_ADDRESS)
    for value in _unique(seed.attack_type_raws):
        append_item("attack_type", value, f"Attack type candidate: {value}.", seed_source, CONFIDENCE_ATTACK_TYPE_CANDIDATE, inferred=True)
    for value in _unique(seed.summary_candidates + seed.note_candidates):
        append_item("summary_candidate", value[:300], value, seed_source, CONFIDENCE_SUMMARY_CANDIDATE, inferred=True)

    for document in source_documents["documents"]:
        if document["title"]:
            append_item(
                "source_title",
                document["title"],
                f"Fetched source title: {document['title']}.",
                document["url"],
                CONFIDENCE_SOURCE_TITLE_FETCHED if document["fetch_status"] == "fetched" else CONFIDENCE_SOURCE_TITLE_UNFETCHED,
            )
        for tx_hash in document["extracted_tx_hashes"][:5]:
            append_item("mentioned_transaction", tx_hash, f"Source text mentions transaction {tx_hash}.", document["url"], CONFIDENCE_MENTIONED_TX, inferred=True)
        for address in document["extracted_addresses"][:8]:
            append_item("mentioned_address", address, f"Source text mentions address {address}.", document["url"], CONFIDENCE_MENTIONED_ADDRESS, inferred=True)

    return {"incident_id": seed.incident_id, "evidence_items": evidence_items}


def build_citation_graph(raw_evidence: dict[str, Any]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for item in raw_evidence["evidence_items"]:
        claim_id = f"claim-{len(claims) + 1:03d}"
        claims.append(
            {
                "claim_id": claim_id,
                "claim_text": item["fact_text"],
                "fact_type": item["fact_type"],
                "source_ref": item["source_ref"],
                "source_url": item["source_url"],
                "confidence": item["confidence"],
                "is_inferred": item["is_inferred"],
            }
        )
        if item["source_ref"]:
            edges.append({"from": claim_id, "to": item["source_ref"], "edge_type": "supported_by"})
    return {"incident_id": raw_evidence["incident_id"], "claims": claims, "edges": edges, "conflicts": []}


def build_timeline(seed: IncidentSeed, raw_evidence: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if seed.incident_date:
        steps.append(
            {
                "step_id": "step-001",
                "order": 1,
                "label": "Incident enters the corpus",
                "step_type": "entry",
                "summary": f"{seed.incident_name or seed.protocol_name or 'Incident'} is dated {seed.incident_date}.",
                "source_refs": [],
                "confidence": 0.92,
            }
        )
    if seed.attack_tx_hashes:
        steps.append(
            {
                "step_id": f"step-{len(steps) + 1:03d}",
                "order": len(steps) + 1,
                "label": "Exploit transaction linked",
                "step_type": "exploit",
                "summary": f"The current dossier has {len(seed.attack_tx_hashes)} direct attack transaction candidate(s).",
                "source_refs": [
                    item["source_ref"]
                    for item in raw_evidence["evidence_items"]
                    if item["fact_type"] == "attack_transaction" and item["source_ref"]
                ],
                "confidence": 0.9,
            }
        )
    if seed.summary_candidates:
        steps.append(
            {
                "step_id": f"step-{len(steps) + 1:03d}",
                "order": len(steps) + 1,
                "label": "Impact summary collected",
                "step_type": "impact",
                "summary": seed.summary_candidates[0][:260],
                "source_refs": [],
                "confidence": 0.72,
            }
        )
    steps.append(
        {
            "step_id": f"step-{len(steps) + 1:03d}",
            "order": len(steps) + 1,
            "label": "Source expansion completed",
            "step_type": "analysis",
            "summary": "The pipeline fetched seed sources, extracted direct clues, and discovered second-hop links for later runs.",
            "source_refs": [],
            "confidence": 0.75,
        }
    )
    return {"incident_id": seed.incident_id, "steps": steps}


def build_attacker_profile(seed: IncidentSeed, raw_evidence: dict[str, Any]) -> dict[str, Any]:
    primary = _unique(seed.attacker_addresses)
    mentioned = _unique(
        item["fact_value"]
        for item in raw_evidence["evidence_items"]
        if item["fact_type"] == "mentioned_address"
    )
    summary = (
        f"The dossier has {len(primary)} direct attacker address candidate(s) and {len(mentioned)} additional address mentions from fetched sources."
        if primary or mentioned
        else "No strong attacker address has been confirmed yet; the system only has indirect source clues so far."
    )
    return {
        "incident_id": seed.incident_id,
        "profile_id": f"profile-{seed.incident_id}",
        "primary_addresses": primary,
        "related_addresses": mentioned[:10],
        "related_address_count": len(mentioned),
        "funding_source": "Not confirmed",
        "deployment_to_attack_time": "Not confirmed",
        "pre_attack_activity": "Not confirmed",
        "post_attack_fund_flow": "Not confirmed",
        "evidence_refs": [
            item["source_ref"]
            for item in raw_evidence["evidence_items"]
            if item["fact_type"] == "mentioned_address" and item.get("source_ref")
        ][:8],
        "confidence": "partial" if primary or mentioned else "low",
        "recent_activity_summary": summary,
        "counterparties": [],
        "repeated_behaviors": [
            "Leans on addresses confirmed by direct seed fields first.",
            "Uses source-text mentions as weaker supporting clues rather than direct proof.",
        ],
        "open_questions": [
            "Which address funded the exploit wallet before the attack?",
            "Which transfers right after the exploit are still missing from the dossier?",
        ],
    }


def build_pattern_hypotheses(seed: IncidentSeed, raw_evidence: dict[str, Any]) -> dict[str, Any]:
    combined = " ".join(seed.tags + seed.attack_type_raws + [item["fact_text"] for item in raw_evidence["evidence_items"]]).lower()
    label = "unknown"
    summary = "The system does not yet have enough technical evidence to name the exploit pattern confidently."
    confidence = 0.35
    why = ["Only a partial evidence graph is available."]
    if "price" in combined and "manip" in combined:
        label = "price_manipulation"
        summary = "Multiple seed and source cues point to a price-manipulation style exploit."
        confidence = 0.76
        why = ["Attack-type tags mention price manipulation.", "The supporting sources resemble prior price-manipulation writeups."]
    elif "oracle" in combined:
        label = "oracle_manipulation"
        summary = "There are oracle-related cues, but the mechanism still needs stronger direct evidence."
        confidence = 0.61
        why = ["At least one source cue mentions oracle behavior."]
    return {
        "incident_id": seed.incident_id,
        "hypotheses": [
            {
                "hypothesis_id": "hyp-001",
                "label": label,
                "summary": summary,
                "why_suspected": why,
                "confidence": confidence,
                "open_questions": [
                    "Which specific pricing path was abused?",
                    "Is there a direct explorer or postmortem source that confirms the same mechanism?",
                ],
            }
        ],
    }


def build_quality_report(seed: IncidentSeed, source_index: dict[str, Any], source_documents: dict[str, Any], raw_evidence: dict[str, Any]) -> dict[str, Any]:
    direct_sources = [item for item in source_index["sources"] if item["depth"] == 0]
    secondary_sources = [item for item in source_index["sources"] if item["depth"] > 0]
    fetched_docs = [item for item in source_documents["documents"] if item["fetch_status"] == "fetched"]
    cited_claims = [item for item in raw_evidence["evidence_items"] if item["source_ref"]]

    mentioned_transactions = [
        item["fact_value"]
        for item in raw_evidence["evidence_items"]
        if item["fact_type"] == "mentioned_transaction"
    ]
    missing_fields: list[str] = []
    if not seed.attack_tx_hashes and not mentioned_transactions:
        missing_fields.append("attack_tx_hashes")
    if not seed.attack_contract_urls:
        missing_fields.append("attack_contract_urls")
    if not seed.victim_contract_urls:
        missing_fields.append("victim_contract_urls")
    if not any(item["source_type"] == "social" for item in source_index["sources"]):
        missing_fields.append("social_sources")
    if not any(item["source_type"] == "poc" for item in source_index["sources"]):
        missing_fields.append("poc_links")

    total_checks = 7
    filled_checks = 0
    filled_checks += 1 if (seed.attack_tx_hashes or mentioned_transactions) else 0
    filled_checks += 1 if seed.attack_contract_urls else 0
    filled_checks += 1 if seed.victim_contract_urls else 0
    filled_checks += 1 if direct_sources else 0
    filled_checks += 1 if secondary_sources else 0
    filled_checks += 1 if any(item["source_type"] == "poc" for item in source_index["sources"]) else 0
    filled_checks += 1 if any(item["source_type"] == "social" for item in source_index["sources"]) else 0
    completeness_score = round(filled_checks / total_checks, 2)

    return {
        "incident_id": seed.incident_id,
        "completeness_score": completeness_score,
        "direct_source_count": len(direct_sources),
        "secondary_source_count": len(secondary_sources),
        "fetched_source_count": len(fetched_docs),
        "citation_coverage_count": len(cited_claims),
        "missing_fields": missing_fields,
        "judge_summary": (
            "This run is strong enough for demo browsing, but still needs more direct technical evidence before it should be treated as a full analyst-grade dossier."
            if completeness_score >= 0.6
            else "This run is still a partial dossier and should be treated as a work-in-progress build."
        ),
    }


def merge_technical_analysis(
    timeline: dict[str, Any],
    attacker_profile: dict[str, Any],
    augmented_summary: str,
    technical_analysis: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if not technical_analysis:
        return timeline, attacker_profile, augmented_summary

    merge_back = technical_analysis.get("merge_back") or {}
    technical_steps = merge_back.get("timeline_steps") or []
    if technical_steps:
        normalized_technical_steps = []
        for step in technical_steps:
            normalized_technical_steps.append(
                {
                    **step,
                    "summary": step.get("summary") or step.get("detail") or step.get("title") or "",
                }
            )
        timeline = {
            **timeline,
            "steps": normalized_technical_steps + timeline.get("steps", []),
        }

    technical_addresses = merge_back.get("key_addresses") or []
    if technical_addresses:
        attacker_profile = {
            **attacker_profile,
            "primary_addresses": _unique(technical_addresses + attacker_profile.get("primary_addresses", [])),
            "related_address_count": len(_unique(technical_addresses + attacker_profile.get("related_addresses", []))),
            "confidence": "partial",
        }

    technical_flow = merge_back.get("funds_flow_path") or []
    if technical_flow:
        attacker_profile = {
            **attacker_profile,
            "post_attack_fund_flow": f"Technical analysis identified {len(technical_flow)} fund-flow step(s).",
        }

    external_validation = merge_back.get("external_validation") or {}
    if external_validation.get("status") == "completed":
        attacker_profile = {
            **attacker_profile,
            "evidence_refs": _unique(
                attacker_profile.get("evidence_refs", [])
                + [
                    artifact
                    for tx in external_validation.get("transactions", [])
                    for artifact in (tx.get("artifacts") or {}).values()
                ]
            )[:8],
        }

    summary = merge_back.get("summary") or augmented_summary
    return timeline, attacker_profile, summary


def build_augmented_incident(
    seed: IncidentSeed,
    source_index: dict[str, Any],
    source_documents: dict[str, Any],
    raw_evidence: dict[str, Any],
    timeline: dict[str, Any],
    attacker_profile: dict[str, Any],
    pattern_hypotheses: dict[str, Any],
    quality_report: dict[str, Any],
    technical_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = seed.incident_name or f"{seed.protocol_name or 'Unknown protocol'} incident"
    source_types = Counter(item["source_type"] for item in source_index["sources"])
    summary = (
        seed.summary_candidates[0]
        if seed.summary_candidates
        else seed.note_candidates[0]
        if seed.note_candidates
        else f"The dossier for {title} was rebuilt from seed links, fetched source pages, and second-hop source expansion."
    )
    mentioned_transactions = _unique(
        item["fact_value"]
        for item in raw_evidence["evidence_items"]
        if item["fact_type"] == "mentioned_transaction"
    )
    mentioned_addresses = _unique(
        item["fact_value"]
        for item in raw_evidence["evidence_items"]
        if item["fact_type"] == "mentioned_address"
    )
    payload = {
        "incident_id": seed.incident_id,
        "title": title,
        "incident_date": _best_incident_date(seed),
        "chain": seed.chain,
        "protocol_name": seed.protocol_name or seed.incident_name,
        "status": "demo_live_dossier",
        "summary": summary,
        "seed_overview": {
            "seed_type": seed.seed_type,
            "trigger_type": seed.trigger_type,
            "source_names": seed.source_names,
            "attack_type_raws": seed.attack_type_raws,
        },
        "key_addresses": _unique(seed.attacker_addresses + attacker_profile["related_addresses"][:4] + mentioned_addresses[:4]),
        "key_contracts": _unique(seed.attack_contract_urls + seed.victim_contract_urls),
        "key_transactions": _unique(seed.attack_tx_hashes + mentioned_transactions[:4]),
        "timeline": timeline["steps"],
        "attacker_profile": attacker_profile,
        "pattern_hypotheses": pattern_hypotheses["hypotheses"],
        "source_summary": {
            "source_count": len(source_index["sources"]),
            "source_types": dict(source_types),
            "direct_source_count": quality_report["direct_source_count"],
            "secondary_source_count": quality_report["secondary_source_count"],
            "fetched_source_count": quality_report["fetched_source_count"],
        },
        "quality_report": quality_report,
        "generated_at": utc_now_iso(),
    }
    if technical_analysis:
        payload["technical_analysis"] = {
            "status": technical_analysis.get("status", "unknown"),
            "primary_tx_hash": technical_analysis.get("primary_tx_hash", ""),
            "tx_hashes": technical_analysis.get("tx_hashes", []),
            "exploit_mechanism": technical_analysis.get("reasoning", {}).get("exploit_mechanism", ""),
            "validation_verdict": technical_analysis.get("validation", {}).get("verdict", ""),
            "external_enrichment": technical_analysis.get("external_enrichment", {"status": "unavailable"}),
        }
    return payload


def build_dashboard_view(augmented_incident: dict[str, Any]) -> dict[str, Any]:
    timeline = augmented_incident["timeline"]
    quality = augmented_incident["quality_report"]
    hypotheses = augmented_incident["pattern_hypotheses"]
    return {
        "incident_id": augmented_incident["incident_id"],
        "card": {
            "title": augmented_incident["title"],
            "chain": augmented_incident["chain"],
            "incident_date": augmented_incident["incident_date"],
            "protocol_name": augmented_incident["protocol_name"],
            "summary": augmented_incident["summary"],
            "source_count": augmented_incident["source_summary"]["source_count"],
            "direct_source_count": augmented_incident["source_summary"]["direct_source_count"],
            "secondary_source_count": augmented_incident["source_summary"]["secondary_source_count"],
            "completeness_score": quality["completeness_score"],
        },
        "detail": {
            "timeline_preview": timeline[:4],
            "attacker_profile_summary": augmented_incident["attacker_profile"]["recent_activity_summary"],
            "pattern_summary": hypotheses[0]["summary"] if hypotheses else "",
            "judge_summary": quality["judge_summary"],
            "missing_fields": quality["missing_fields"],
            "technical_analysis_status": augmented_incident.get("technical_analysis", {}).get("status", "not_requested"),
        },
        "status": augmented_incident["status"],
        "last_updated": augmented_incident["generated_at"],
    }


def build_report_inputs(augmented_incident: dict[str, Any], source_index: dict[str, Any]) -> dict[str, Any]:
    hypotheses = augmented_incident["pattern_hypotheses"]
    return {
        "incident_id": augmented_incident["incident_id"],
        "headline": augmented_incident["title"],
        "executive_summary": augmented_incident["summary"],
        "timeline_summary": " ".join(
            step.get("summary") or step.get("detail") or step.get("title") or ""
            for step in augmented_incident["timeline"][:4]
        ),
        "attacker_behavior_summary": augmented_incident["attacker_profile"]["recent_activity_summary"],
        "pattern_summary": hypotheses[0]["summary"] if hypotheses else "",
        "source_refs": [
            {"source_id": item["source_id"], "url": item["url"], "source_type": item["source_type"], "depth": item["depth"]}
            for item in source_index["sources"]
        ],
        "open_questions": hypotheses[0]["open_questions"] if hypotheses else [],
    }


def build_incident_library_entry(augmented_incident: dict[str, Any], source_index: dict[str, Any]) -> dict[str, Any]:
    quality = augmented_incident["quality_report"]
    source_types = augmented_incident["source_summary"]["source_types"]
    return {
        "incident_id": augmented_incident["incident_id"],
        "title": augmented_incident["title"],
        "protocol_name": augmented_incident["protocol_name"],
        "chain": augmented_incident["chain"],
        "incident_date": augmented_incident["incident_date"],
        "summary": augmented_incident["summary"],
        "status": augmented_incident["status"],
        "completeness_score": quality["completeness_score"],
        "source_count": augmented_incident["source_summary"]["source_count"],
        "direct_source_count": quality["direct_source_count"],
        "secondary_source_count": quality["secondary_source_count"],
        "social_count": source_types.get("social", 0),
        "poc_count": source_types.get("poc", 0),
        "explorer_count": source_types.get("explorer", 0),
        "report_count": source_types.get("report", 0),
        "missing_fields": quality["missing_fields"],
        "last_updated": augmented_incident["generated_at"],
        "pattern_label": augmented_incident["pattern_hypotheses"][0]["label"] if augmented_incident["pattern_hypotheses"] else "unknown",
        "attack_tx_hashes": augmented_incident["key_transactions"],
        "source_preview": [item["url"] for item in source_index["sources"][:6]],
    }


def merge_technical_analysis_into_report(report: dict[str, Any], technical_analysis: dict[str, Any] | None) -> dict[str, Any]:
    if not technical_analysis:
        return report

    merge_back = technical_analysis.get("merge_back") or {}
    funds_flow_path = merge_back.get("funds_flow_path") or []
    if funds_flow_path:
        report["fund_flow"] = {
            **report.get("fund_flow", {}),
            "summary": f"Technical analysis traced transaction-level fund movement across {len(funds_flow_path)} step(s).",
            "key_transactions": merge_back.get("key_transactions", report.get("fund_flow", {}).get("key_transactions", [])),
            "key_addresses": merge_back.get("key_addresses", report.get("fund_flow", {}).get("key_addresses", [])),
            "path": funds_flow_path,
        }
    report["open_questions"] = merge_back.get("open_questions", report.get("open_questions", []))
    return report


def _record_event(events: list[dict[str, Any]], stage: str, status: str, note: str, artifact_paths: list[str] | None = None, metrics: dict[str, Any] | None = None, error_message: str = "") -> None:
    events.append(
        {
            "event_id": f"evt-{len(events) + 1:03d}",
            "timestamp": utc_now_iso(),
            "stage": stage,
            "agent": AGENTS.get(stage, stage),
            "status": status,
            "note": note,
            "artifact_paths": artifact_paths or [],
            "metrics": metrics or {},
            "error_message": error_message,
        }
    )


def _append_agent_trace(traces: list[dict[str, Any]], stage: str, started_at: str, outputs: list[str], metrics: dict[str, Any] | None = None, status: str = "completed", note: str = "") -> None:
    traces.append(
        {
            "agent_id": stage,
            "agent_name": AGENTS.get(stage, stage),
            "started_at": started_at,
            "completed_at": utc_now_iso(),
            "status": status,
            "outputs": outputs,
            "metrics": metrics or {},
            "note": note,
        }
    )


def run_augmentation_mvp(seed_path: str | Path, runs_dir: str | Path = "runs") -> Path:
    seed = load_seed(seed_path)
    run_dir = Path(runs_dir) / seed.incident_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("pipeline.started", extra={"incident_id": seed.incident_id, "run_dir": str(run_dir)})

    run_state = RunState.for_seed(seed)
    run_events: list[dict[str, Any]] = []
    agent_trace: list[dict[str, Any]] = []
    try:
        return _run_augmentation_stages(seed, run_dir, run_state, run_events, agent_trace)
    except Exception as exc:
        run_state.current_stage = "failed"
        run_state.updated_at = utc_now_iso()
        run_state.run_notes.append(str(exc))
        write_json(run_dir / "run_state.json", run_state.to_dict())
        logger.error(
            "pipeline.failed",
            extra={"incident_id": seed.incident_id, "error": str(exc)},
            exc_info=True,
        )
        raise


def _run_qa_retry_pass(
    *,
    seed: "IncidentSeed",
    run_dir: Path,
    pipeline_trace: TraceCollector,
    first_pass_raw_evidence: dict[str, Any],
    first_pass_timeline: dict[str, Any],
    first_pass_narrative: dict[str, Any],
    first_pass_quality_report: dict[str, Any],
    source_index: dict[str, Any],
    source_documents: dict[str, Any],
    llm_raw_evidence_pre: dict[str, Any],
    heuristic_quality: dict[str, Any],
    heuristic_timeline: dict[str, Any],
) -> dict[str, Any]:
    """Run a single QA retry pass when the first-pass quality is below threshold.

    Returns a dict with keys:
      raw_evidence, timeline, narrative, quality_report  (promoted v2 if retry succeeded, else first-pass)
      qa_retry_triggered: bool
      qa_retry_critique: str | None
    """
    first_pass_score = first_pass_quality_report.get("completeness_score", 1.0)
    missing_dimensions = (
        first_pass_quality_report.get("missing_dimensions")
        or first_pass_quality_report.get("missing_fields")
        or []
    )
    needs_retry = first_pass_score < QA_RETRY_SCORE_THRESHOLD or bool(missing_dimensions)

    result: dict[str, Any] = {
        "raw_evidence": first_pass_raw_evidence,
        "timeline": first_pass_timeline,
        "narrative": first_pass_narrative,
        "quality_report": first_pass_quality_report,
        "qa_retry_triggered": False,
        "qa_retry_critique": None,
    }

    if not needs_retry:
        return result

    critique_parts = [
        f"First-pass completeness score: {first_pass_score:.2f} (threshold: {QA_RETRY_SCORE_THRESHOLD}).",
    ]
    if missing_dimensions:
        critique_parts.append(
            f"Missing/weak dimensions: {', '.join(str(d) for d in missing_dimensions)}."
        )
    judge_summary = first_pass_quality_report.get("judge_summary", "")
    if judge_summary:
        critique_parts.append(f"Quality assessor notes: {judge_summary}")
    gaps = first_pass_quality_report.get("gaps", [])
    if gaps:
        critique_parts.append(f"Identified gaps: {'; '.join(str(g) for g in gaps)}.")
    recommendations = first_pass_quality_report.get("recommendations", [])
    if recommendations:
        critique_parts.append(f"Recommendations: {'; '.join(str(r) for r in recommendations)}.")
    critique = " ".join(critique_parts)
    result["qa_retry_critique"] = critique

    logger.info(
        "qa_retry.triggered",
        extra={
            "incident_id": seed.incident_id,
            "first_pass_score": first_pass_score,
            "missing_dimensions": missing_dimensions,
            "critique_chars": len(critique),
        },
    )

    try:
        pipeline_trace.set_qa_retry(critique)
        with pipeline_trace.record(
            "evidence_extractor",
            agent_type="llm",
            input_summary=f"RETRY: {len(source_documents.get('documents', []))} docs; critique injected",
            notes="QA retry pass; tokens: not captured (response parsed internally)",
        ) as slot_ee2:
            retry_raw_evidence = run_llm_evidence_extractor(
                seed_dict=seed.to_dict(),
                source_documents=source_documents,
                existing_raw_evidence=llm_raw_evidence_pre,
                incident_id=seed.incident_id,
                retry_critique=critique,
            )
            slot_ee2.output_summary = (
                f"{len(retry_raw_evidence.get('evidence_items', []))} items after retry extraction"
            )

        retry_evidence_items = retry_raw_evidence.get("evidence_items", [])
        with pipeline_trace.record(
            "timeline_synthesizer",
            agent_type="llm",
            input_summary=f"RETRY: {len(retry_evidence_items)} evidence items",
            notes="QA retry pass; tokens: not captured (response parsed internally)",
        ) as slot_ts2, pipeline_trace.record(
            "narrative_writer",
            agent_type="llm",
            input_summary=f"RETRY: {len(retry_evidence_items)} evidence items",
            notes="QA retry pass; tokens: not captured (response parsed internally)",
        ) as slot_nw2:
            with _LLMExecutor(max_workers=2) as executor:
                future_timeline = executor.submit(
                    run_llm_timeline_synthesizer,
                    seed.to_dict(), retry_evidence_items, heuristic_timeline, seed.incident_id,
                )
                future_narrative = executor.submit(
                    run_llm_narrative_writer,
                    seed.to_dict(), retry_evidence_items, seed.incident_id,
                )
                retry_timeline = future_timeline.result()
                retry_narrative = future_narrative.result()
            slot_ts2.output_summary = f"{len(retry_timeline.get('steps', []))} timeline steps (v2)"
            slot_nw2.output_summary = (
                f"executive_summary len={len(str(retry_narrative.get('executive_summary', '')))} (v2)"
            )

        for step in retry_timeline.get("steps", []):
            step.setdefault("summary", step.get("action", ""))

        with pipeline_trace.record(
            "quality_assessor",
            agent_type="llm",
            input_summary=f"RETRY: {len(retry_timeline.get('steps', []))} steps; {len(retry_narrative)} narrative keys",
            notes="QA retry pass; tokens: not captured (response parsed internally)",
        ) as slot_qa2:
            retry_quality_report = run_llm_quality_assessor(
                seed_dict=seed.to_dict(),
                dossier_draft={
                    "timeline": retry_timeline,
                    "narrative": retry_narrative,
                    "evidence_items": retry_raw_evidence.get("evidence_items", []),
                    "source_count": len(source_index.get("sources", [])),
                    "heuristic_missing_fields": heuristic_quality.get("missing_fields", []),
                    "heuristic_quality_report": heuristic_quality,
                },
                incident_id=seed.incident_id,
            )
            slot_qa2.output_summary = (
                f"v2 completeness_score={retry_quality_report.get('completeness_score', '?')}"
            )
        retry_quality_report = {**heuristic_quality, **retry_quality_report}
        retry_quality_report["completeness_score"] = normalize_completeness_score(
            retry_quality_report.get("completeness_score", 0)
        )

        logger.info(
            "qa_retry.completed",
            extra={
                "incident_id": seed.incident_id,
                "v2_score": retry_quality_report.get("completeness_score"),
            },
        )

        retry_dir = run_dir / "qa_retry"
        retry_dir.mkdir(exist_ok=True)
        write_json(retry_dir / "raw_evidence_v2.json", retry_raw_evidence)
        write_json(retry_dir / "timeline_v2.json", retry_timeline)
        write_json(retry_dir / "narrative_v2.json", retry_narrative)
        write_json(retry_dir / "quality_report_v2.json", retry_quality_report)

        # Overwrite the main artifacts so downstream reads are consistent
        write_json(run_dir / "timeline.json", retry_timeline)
        write_json(run_dir / "narrative.json", retry_narrative)
        write_json(run_dir / "raw_evidence.json", retry_raw_evidence)

        result.update(
            raw_evidence=retry_raw_evidence,
            timeline=retry_timeline,
            narrative=retry_narrative,
            quality_report=retry_quality_report,
            qa_retry_triggered=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "qa_retry.failed",
            extra={"incident_id": seed.incident_id, "error": str(exc)},
        )
        # Keep first-pass results; critique stays set so trace records the attempt

    return result


def _run_augmentation_stages(
    seed: "IncidentSeed",
    run_dir: Path,
    run_state: "RunState",
    run_events: list[dict[str, Any]],
    agent_trace: list[dict[str, Any]],
) -> Path:
    pipeline_trace = TraceCollector()

    write_json(run_dir / "incident_seed.json", seed.to_dict())
    run_state.mark_stage("seed_loader", note="Loaded and normalized incident seed.", artifact_name="incident_seed", artifact_path=str(run_dir / "incident_seed.json"))
    write_json(run_dir / "run_state.json", run_state.to_dict())
    _record_event(run_events, "seed_loader", "completed", "Loaded incident seed.", [str(run_dir / "incident_seed.json")])

    stage_started = utc_now_iso()
    _t = time.perf_counter()
    source_index = build_source_index(seed)
    write_json(run_dir / "source_index.json", source_index)
    run_state.mark_stage("source_finder", note="Built direct source candidates from seed facts.", artifact_name="source_index", artifact_path=str(run_dir / "source_index.json"))
    _record_event(
        run_events,
        "source_finder",
        "completed",
        "Ranked direct source candidates.",
        [str(run_dir / "source_index.json")],
        {"source_count": len(source_index["sources"])},
    )
    _append_agent_trace(agent_trace, "source_finder", stage_started, [str(run_dir / "source_index.json")], {"source_count": len(source_index["sources"])})
    logger.info("stage.completed", extra={"stage": "source_finder", "incident_id": seed.incident_id, "source_count": len(source_index["sources"]), "duration_ms": round((time.perf_counter() - _t) * 1000)})
    write_json(run_dir / "run_state.json", run_state.to_dict())

    stage_started = utc_now_iso()
    _t = time.perf_counter()
    source_index, source_documents = expand_sources(source_index)
    write_json(run_dir / "source_index.json", source_index)
    write_json(run_dir / "source_documents.json", source_documents)
    run_state.mark_stage("source_expander", note="Fetched direct sources and discovered second-hop links.", artifact_name="source_documents", artifact_path=str(run_dir / "source_documents.json"))
    _record_event(
        run_events,
        "source_expander",
        "completed",
        "Fetched source pages and extracted discovered links.",
        [str(run_dir / "source_index.json"), str(run_dir / "source_documents.json")],
        {
            "source_count": len(source_index["sources"]),
            "fetched_documents": len(source_documents["documents"]),
        },
    )
    _append_agent_trace(
        agent_trace,
        "source_expander",
        stage_started,
        [str(run_dir / "source_index.json"), str(run_dir / "source_documents.json")],
        {"source_count": len(source_index["sources"]), "fetched_documents": len(source_documents["documents"])},
    )
    logger.info("stage.completed", extra={"stage": "source_expander", "incident_id": seed.incident_id, "source_count": len(source_index["sources"]), "fetched_documents": len(source_documents["documents"]), "duration_ms": round((time.perf_counter() - _t) * 1000)})
    write_json(run_dir / "run_state.json", run_state.to_dict())

    # --- LLM Stage 1: Evidence Extractor ---
    _t_llm = time.perf_counter()
    run_state.mark_stage("llm_evidence_extractor", status="running")
    write_json(run_dir / "run_state.json", run_state.to_dict())
    _llm_raw_evidence_pre = build_raw_evidence(seed, source_index, source_documents)
    with pipeline_trace.record(
        "evidence_extractor",
        agent_type="llm",
        input_summary=f"{len(source_documents.get('documents', []))} source docs; {len(_llm_raw_evidence_pre.get('evidence_items', []))} heuristic items",
        notes="tokens: not captured (response parsed internally)",
    ) as _slot_ee:
        _llm_evidence_enriched = run_llm_evidence_extractor(
            seed_dict=seed.to_dict(),
            source_documents=source_documents,
            existing_raw_evidence=_llm_raw_evidence_pre,
            incident_id=seed.incident_id,
        )
        _slot_ee.output_summary = (
            f"{len(_llm_evidence_enriched.get('evidence_items', []))} total items "
            f"(+{len(_llm_evidence_enriched.get('evidence_items', [])) - len(_llm_raw_evidence_pre.get('evidence_items', []))} LLM-extracted)"
        )
    run_state.mark_stage("llm_evidence_extractor", status="completed", note=f"LLM extracted {len(_llm_evidence_enriched.get('evidence_items', [])) - len(_llm_raw_evidence_pre.get('evidence_items', []))} extra items.")
    logger.info("stage.completed", extra={"stage": "llm_evidence_extractor", "incident_id": seed.incident_id, "duration_ms": round((time.perf_counter() - _t_llm) * 1000)})
    write_json(run_dir / "run_state.json", run_state.to_dict())

    stage_started = utc_now_iso()
    _t = time.perf_counter()
    raw_evidence = _llm_evidence_enriched  # use LLM-enriched evidence
    citation_graph = build_citation_graph(raw_evidence)
    write_json(run_dir / "raw_evidence.json", raw_evidence)
    write_json(run_dir / "citation_graph.json", citation_graph)
    run_state.mark_stage("evidence_normalizer", note="Turned fetched sources into citation-backed evidence.", artifact_name="raw_evidence", artifact_path=str(run_dir / "raw_evidence.json"))
    _record_event(
        run_events,
        "evidence_normalizer",
        "completed",
        "Normalized source text into evidence items and citation edges.",
        [str(run_dir / "raw_evidence.json"), str(run_dir / "citation_graph.json")],
        {"evidence_count": len(raw_evidence["evidence_items"]), "claim_count": len(citation_graph["claims"])},
    )
    _append_agent_trace(
        agent_trace,
        "evidence_normalizer",
        stage_started,
        [str(run_dir / "raw_evidence.json"), str(run_dir / "citation_graph.json")],
        {"evidence_count": len(raw_evidence["evidence_items"]), "claim_count": len(citation_graph["claims"])},
    )
    logger.info("stage.completed", extra={"stage": "evidence_normalizer", "incident_id": seed.incident_id, "evidence_count": len(raw_evidence["evidence_items"]), "duration_ms": round((time.perf_counter() - _t) * 1000)})
    write_json(run_dir / "run_state.json", run_state.to_dict())

    stage_started = utc_now_iso()
    _t = time.perf_counter()
    run_state.mark_stage("technical_deterministic_collection", status="running")
    write_json(run_dir / "run_state.json", run_state.to_dict())
    technical_analysis = run_incident_technical_analysis(
        seed=seed,
        run_dir=run_dir,
        source_context={
            "summary": (seed.summary_candidates[0] if seed.summary_candidates else ""),
        },
        trace=pipeline_trace,
    )
    if technical_analysis.get("status") == "completed":
        run_state.mark_stage("technical_deterministic_collection", status="completed")
        run_state.mark_stage("technical_reasoning", status="completed")
        run_state.mark_stage("technical_validation", status="completed")
    elif technical_analysis.get("status") == "skipped":
        run_state.mark_stage("technical_deterministic_collection", status="completed", note="Skipped because no configured RPC or attack tx was available.")
        run_state.mark_stage("technical_reasoning", status="completed")
        run_state.mark_stage("technical_validation", status="completed")
    else:
        run_state.mark_stage("technical_deterministic_collection", status="completed")
        run_state.mark_stage("technical_reasoning", status="completed")
        run_state.mark_stage("technical_validation", status="completed", note=technical_analysis.get("validation", {}).get("verdict", "Technical analysis completed with gaps."))
    _record_event(
        run_events,
        "technical_validation",
        "completed",
        technical_analysis.get("validation", {}).get("verdict", "Technical analysis finished."),
        [str(run_dir / "technical_analysis.json")],
        {
            "technical_status": technical_analysis.get("status", "unknown"),
            "checked_transactions": technical_analysis.get("validation", {}).get("checked_transactions", 0),
        },
    )
    _append_agent_trace(
        agent_trace,
        "technical_validation",
        stage_started,
        [str(run_dir / "technical_analysis.json")],
        {
            "technical_status": technical_analysis.get("status", "unknown"),
            "checked_transactions": technical_analysis.get("validation", {}).get("checked_transactions", 0),
        },
        note=technical_analysis.get("validation", {}).get("verdict", ""),
    )
    logger.info(
        "stage.completed",
        extra={
            "stage": "technical_analysis",
            "incident_id": seed.incident_id,
            "technical_status": technical_analysis.get("status", "unknown"),
            "duration_ms": round((time.perf_counter() - _t) * 1000),
        },
    )
    write_json(run_dir / "run_state.json", run_state.to_dict())

    # Heuristic timeline and profile (always computed — used as fallback for Agent 2)
    _heuristic_timeline = build_timeline(seed, raw_evidence)
    attacker_profile = build_attacker_profile(seed, raw_evidence)
    pattern_hypotheses = build_pattern_hypotheses(seed, raw_evidence)

    # --- LLM Stages 2 & 3: Timeline Synthesizer + Narrative Writer (parallel) ---
    stage_started = utc_now_iso()
    _t = time.perf_counter()
    run_state.mark_stage("llm_timeline_synthesizer", status="running")
    run_state.mark_stage("llm_narrative_writer", status="running")
    write_json(run_dir / "run_state.json", run_state.to_dict())

    evidence_items_for_llm = raw_evidence.get("evidence_items", [])
    with pipeline_trace.record(
        "timeline_synthesizer",
        agent_type="llm",
        input_summary=f"{len(evidence_items_for_llm)} evidence items",
        notes="tokens: not captured (response parsed internally)",
    ) as _slot_ts, pipeline_trace.record(
        "narrative_writer",
        agent_type="llm",
        input_summary=f"{len(evidence_items_for_llm)} evidence items",
        notes="tokens: not captured (response parsed internally)",
    ) as _slot_nw:
        with _LLMExecutor(max_workers=2) as _exec:
            _future_timeline = _exec.submit(
                run_llm_timeline_synthesizer, seed.to_dict(), evidence_items_for_llm, _heuristic_timeline, seed.incident_id
            )
            _future_narrative = _exec.submit(
                run_llm_narrative_writer, seed.to_dict(), evidence_items_for_llm, seed.incident_id
            )
            timeline = _future_timeline.result()
            narrative = _future_narrative.result()
        _slot_ts.output_summary = f"{len(timeline.get('steps', []))} timeline steps"
        _slot_nw.output_summary = f"executive_summary len={len(str(narrative.get('executive_summary', '')))}"

    # Normalize timeline steps: LLM uses "action", heuristic uses "summary"
    for step in timeline.get("steps", []):
        step.setdefault("summary", step.get("action", ""))

    summary_seed = (
        seed.summary_candidates[0]
        if seed.summary_candidates
        else seed.note_candidates[0]
        if seed.note_candidates
        else ""
    )
    timeline, attacker_profile, merged_summary = merge_technical_analysis(
        timeline,
        attacker_profile,
        summary_seed,
        technical_analysis,
    )

    run_state.mark_stage("llm_timeline_synthesizer", status="completed")
    run_state.mark_stage("llm_narrative_writer", status="completed")
    logger.info("stage.completed", extra={"stage": "llm_timeline_synthesizer+narrative_writer", "incident_id": seed.incident_id, "timeline_steps": len(timeline.get("steps", [])), "duration_ms": round((time.perf_counter() - _t) * 1000)})

    write_json(run_dir / "timeline.json", timeline)
    write_json(run_dir / "attacker_profile.json", attacker_profile)
    write_json(run_dir / "pattern_hypotheses.json", pattern_hypotheses)
    write_json(run_dir / "narrative.json", narrative)
    write_json(run_dir / "run_state.json", run_state.to_dict())

    _record_event(
        run_events, "llm_timeline_synthesizer", "completed",
        "LLM synthesized attack timeline.",
        [str(run_dir / "timeline.json")],
        {"timeline_steps": len(timeline.get("steps", []))},
    )
    _record_event(
        run_events, "llm_narrative_writer", "completed",
        "LLM wrote incident narrative.",
        [str(run_dir / "narrative.json")],
        {},
    )
    _append_agent_trace(agent_trace, "llm_timeline_synthesizer", stage_started, [str(run_dir / "timeline.json")], {"timeline_steps": len(timeline.get("steps", []))})
    _append_agent_trace(agent_trace, "llm_narrative_writer", stage_started, [str(run_dir / "narrative.json")], {})

    stage_started = utc_now_iso()
    _t = time.perf_counter()
    _heuristic_quality = build_quality_report(seed, source_index, source_documents, raw_evidence)
    # --- LLM Stage 4: Quality Assessor ---
    run_state.mark_stage("llm_quality_assessor", status="running")
    write_json(run_dir / "run_state.json", run_state.to_dict())
    with pipeline_trace.record(
        "quality_assessor",
        agent_type="llm",
        input_summary=f"{len(timeline.get('steps', []))} timeline steps; {len(narrative)} narrative keys",
        notes="tokens: not captured (response parsed internally)",
    ) as _slot_qa:
        quality_report = run_llm_quality_assessor(
            seed_dict=seed.to_dict(),
            dossier_draft={
                "timeline": timeline,
                "narrative": narrative,
                "evidence_items": raw_evidence.get("evidence_items", []),
                "source_count": len(source_index.get("sources", [])),
                "heuristic_missing_fields": _heuristic_quality.get("missing_fields", []),
                "heuristic_quality_report": _heuristic_quality,
            },
            incident_id=seed.incident_id,
        )
        _slot_qa.output_summary = (
            f"completeness_score={quality_report.get('completeness_score', '?')}; "
            f"judge_summary: {str(quality_report.get('judge_summary', ''))[:80]}"
        )
    run_state.mark_stage("llm_quality_assessor", status="completed")
    logger.info("stage.completed", extra={"stage": "llm_quality_assessor", "incident_id": seed.incident_id, "completeness_score": quality_report.get("completeness_score", 0)})

    retry_result = _run_qa_retry_pass(
        seed=seed,
        run_dir=run_dir,
        pipeline_trace=pipeline_trace,
        first_pass_raw_evidence=raw_evidence,
        first_pass_timeline=timeline,
        first_pass_narrative=narrative,
        first_pass_quality_report=quality_report,
        source_index=source_index,
        source_documents=source_documents,
        llm_raw_evidence_pre=_llm_raw_evidence_pre,
        heuristic_quality=_heuristic_quality,
        heuristic_timeline=_heuristic_timeline,
    )
    raw_evidence = retry_result["raw_evidence"]
    timeline = retry_result["timeline"]
    narrative = retry_result["narrative"]
    quality_report = retry_result["quality_report"]
    _qa_retry_triggered = retry_result["qa_retry_triggered"]
    _qa_retry_critique = retry_result["qa_retry_critique"]

    # Merge LLM quality over heuristic so structural count fields are always present
    quality_report = {**_heuristic_quality, **quality_report}
    quality_report["completeness_score"] = normalize_completeness_score(quality_report.get("completeness_score", 0))
    augmented_incident = build_augmented_incident(
        seed=seed,
        source_index=source_index,
        source_documents=source_documents,
        raw_evidence=raw_evidence,
        timeline=timeline,
        attacker_profile=attacker_profile,
        pattern_hypotheses=pattern_hypotheses,
        quality_report=quality_report,
        technical_analysis=technical_analysis,
    )
    # Embed LLM narrative into the augmented incident for frontend display
    augmented_incident["narrative"] = narrative
    if merged_summary:
        augmented_incident["summary"] = merged_summary
    # QA retry metadata — always present so downstream (UI, trace) can read it
    augmented_incident["qa_retry_triggered"] = _qa_retry_triggered
    augmented_incident["qa_retry_critique"] = _qa_retry_critique
    # Pipeline trace — additive; does not affect consumers that don't read it.
    # This is the MERGED trace: rule-based agents from tx_deep_analysis (collector,
    # planner, contract_intelligence, technical_reasoner, semantic_validator) come
    # first because they ran earlier, followed by LLM agents added here.
    _merged_trace_dict = pipeline_trace.to_dict()
    augmented_incident["pipeline_trace"] = _merged_trace_dict

    # Back-patch technical_analysis.json so both files share the same merged trace
    # (backward compat for consumers that read pipeline_trace from technical_analysis.json).
    if technical_analysis and (run_dir / "technical_analysis.json").exists():
        try:
            _ta_on_disk = json.loads((run_dir / "technical_analysis.json").read_text())
            _ta_on_disk["pipeline_trace"] = _merged_trace_dict
            write_json(run_dir / "technical_analysis.json", _ta_on_disk)
        except Exception:  # noqa: BLE001
            pass  # best-effort; do not abort the pipeline

    dashboard_view = build_dashboard_view(augmented_incident)
    report_inputs = build_report_inputs(augmented_incident, source_index)
    incident_library_entry = build_incident_library_entry(augmented_incident, source_index)
    analyst_report = build_analyst_report(
        incident_id=seed.incident_id,
        augmented_incident=augmented_incident,
        source_index=source_index,
        quality_report=quality_report,
        technical_analysis=technical_analysis,
    )
    analyst_report = merge_technical_analysis_into_report(analyst_report, technical_analysis)
    write_json(run_dir / "quality_report.json", quality_report)
    write_json(run_dir / "augmented_incident.json", augmented_incident)
    write_json(run_dir / "dashboard_view.json", dashboard_view)
    write_json(run_dir / "report_inputs.json", report_inputs)
    write_json(run_dir / "incident_library_entry.json", incident_library_entry)
    write_json(run_dir / "analyst_report.json", analyst_report)
    run_state.mark_stage("dossier_assembler", note="Assembled dossier, quality report, and library entry.", artifact_name="augmented_incident", artifact_path=str(run_dir / "augmented_incident.json"))
    _record_event(
        run_events,
        "dossier_assembler",
        "completed",
        "Assembled final dossier outputs and library projection.",
        [
            str(run_dir / "quality_report.json"),
            str(run_dir / "technical_analysis.json"),
            str(run_dir / "augmented_incident.json"),
            str(run_dir / "dashboard_view.json"),
            str(run_dir / "report_inputs.json"),
            str(run_dir / "incident_library_entry.json"),
            str(run_dir / "analyst_report.json"),
        ],
        {"completeness_score": quality_report["completeness_score"]},
    )
    _append_agent_trace(
        agent_trace,
        "dossier_assembler",
        stage_started,
        [
            str(run_dir / "quality_report.json"),
            str(run_dir / "technical_analysis.json"),
            str(run_dir / "augmented_incident.json"),
            str(run_dir / "dashboard_view.json"),
            str(run_dir / "report_inputs.json"),
            str(run_dir / "incident_library_entry.json"),
            str(run_dir / "analyst_report.json"),
        ],
        {"completeness_score": quality_report["completeness_score"]},
    )
    logger.info("stage.completed", extra={"stage": "dossier_assembler", "incident_id": seed.incident_id, "completeness_score": quality_report["completeness_score"], "duration_ms": round((time.perf_counter() - _t) * 1000)})

    run_state.mark_stage("quality_judge", note=quality_report["judge_summary"], artifact_name="quality_report", artifact_path=str(run_dir / "quality_report.json"))
    _record_event(run_events, "quality_judge", "completed", quality_report["judge_summary"], [str(run_dir / "quality_report.json")], {"missing_field_count": len(quality_report["missing_fields"])})
    _append_agent_trace(agent_trace, "quality_judge", utc_now_iso(), [str(run_dir / "quality_report.json")], {"missing_field_count": len(quality_report["missing_fields"])}, note=quality_report["judge_summary"])

    run_state.mark_stage("dashboard_projection", note="Projected live incident library and dossier views.", artifact_name="incident_library_entry", artifact_path=str(run_dir / "incident_library_entry.json"))
    _record_event(run_events, "dashboard_projection", "completed", "Projected outputs for backend and frontend consumers.", [str(run_dir / "incident_library_entry.json"), str(run_dir / "dashboard_view.json")])

    write_json(run_dir / "run_events.json", {"incident_id": seed.incident_id, "events": run_events})
    write_json(run_dir / "agent_trace.json", {"incident_id": seed.incident_id, "agents": agent_trace})
    write_json(run_dir / "run_state.json", run_state.to_dict())
    # Write the new pipeline trace files
    (run_dir / "pipeline_trace.md").write_text(pipeline_trace.to_markdown(), encoding="utf-8")
    logger.info("pipeline.completed", extra={"incident_id": seed.incident_id, "run_dir": str(run_dir), "stages_completed": len(run_state.to_dict().get("stages", []))})
    return run_dir

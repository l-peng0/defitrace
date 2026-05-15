from __future__ import annotations

import csv
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path


DEFIHACKLABS_REPO_BASE = "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/"
HISTORY_CACHE_NAME = "historical_incident_index.json"

_ENTRY_RE = re.compile(r"^\[(\d{8}) ([^\]]+)\]\(([^)]+)\)")
_CHAIN_HINTS = {
    "bsc": "BSC",
    "bnb": "BSC",
    "arbitrum": "Arbitrum",
    "ethereum": "Ethereum",
    "base": "Base",
    "polygon": "Polygon",
}


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _parse_date(raw: str) -> str:
    return datetime.strptime(raw, "%Y%m%d").date().isoformat()


def _normalize_source_url(raw: str) -> str:
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"{DEFIHACKLABS_REPO_BASE}{raw}"


def _humanize_attack_label(link: str) -> str:
    anchor = link.split("#", 1)[-1].lower()
    label = anchor.split("---", 1)[-1] if "---" in anchor else anchor
    label = label.replace("-", " ").strip()
    return label or "price manipulation"


def _infer_chain(name: str, url: str) -> str:
    combined = f"{name} {url}".lower()
    for token, chain in _CHAIN_HINTS.items():
        if token in combined:
            return chain
    return "Unknown"


def _is_relevant_attack(link: str) -> bool:
    anchor = link.lower()
    return any(
        keyword in anchor
        for keyword in (
            "price-manipulation",
            "oracle",
            "bad-oracle",
            "vulnerable-price-dependency",
            "pair-balance-manipulation",
            "reward-manipulation",
            "share-price-manipulation",
        )
    )


def build_defihacklabs_history_index(
    *,
    readme_path: Path,
    since: date | None = None,
    until: date | None = None,
) -> list[dict]:
    entries: list[dict] = []
    for line in readme_path.read_text().splitlines():
        match = _ENTRY_RE.match(line.strip())
        if not match:
            continue
        raw_date, incident_name, raw_link = match.groups()
        incident_date = datetime.strptime(raw_date, "%Y%m%d").date()
        if since and incident_date < since:
            continue
        if until and incident_date > until:
            continue
        if not _is_relevant_attack(raw_link):
            continue

        incident_date_iso = incident_date.isoformat()
        source_url = _normalize_source_url(raw_link)
        attack_label = _humanize_attack_label(raw_link)
        incident_id = f"history-{_slugify(incident_name)}-{incident_date_iso}"
        entries.append(
            {
                "incident_id": incident_id,
                "incident_name": incident_name,
                "protocol_name": incident_name,
                "chain": _infer_chain(incident_name, raw_link),
                "incident_date": incident_date_iso,
                "source_names": ["DeFiHackLabs snapshot"],
                "seed_urls": [source_url],
                "attack_tx_hashes": [],
                "attack_type_raws": [attack_label],
                "summary_candidates": [
                    f"Collected automatically from the DeFiHackLabs historical incident index: {incident_name} ({attack_label})."
                ],
                "note_candidates": [
                    "This entry is a source-derived historical lead. Open it to inspect the original source link and then run a deeper report build if needed."
                ],
                "date_range": {
                    "first_seen": incident_date_iso,
                    "last_seen": incident_date_iso,
                },
                "trigger_type": "historical_source_snapshot",
                "seed_type": "historical_source_snapshot",
                "pattern_label": attack_label.lower().replace(" ", "_"),
            }
        )
    entries.sort(key=lambda item: (item["incident_date"], item["incident_name"].lower()), reverse=True)
    return entries


def write_history_cache(cache_path: Path, entries: list[dict]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "defihacklabs_snapshot",
        "incident_count": len(entries),
        "incidents": entries,
    }
    cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def read_history_cache(cache_path: Path) -> list[dict]:
    if not cache_path.exists():
        return []
    payload = json.loads(cache_path.read_text())
    return payload.get("incidents", [])


def build_primary_source_history_index(*, repo_root: Path) -> list[dict]:
    grouped: dict[str, dict] = {}
    snapshot_files = [
        repo_root / "data" / "history_snapshots" / "web3sec_strict_pm.csv",
        repo_root / "data" / "history_snapshots" / "slowmist_strict_pm.csv",
        repo_root / "data" / "history_snapshots" / "external_explorer_strict_pm.csv",
    ]

    for csv_path in snapshot_files:
        if not csv_path.exists():
            continue
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                incident_date = row.get("incident_date", "").strip()
                project_name = row.get("project_name", "").strip()
                if not incident_date or not project_name:
                    continue
                key = f"{incident_date}::{_slugify(project_name)}"
                entry = grouped.setdefault(
                    key,
                    {
                        "incident_id": f"history-{_slugify(project_name)}-{incident_date}",
                        "incident_name": project_name,
                        "protocol_name": project_name,
                        "chain": row.get("chain", "").strip() or "Unknown",
                        "incident_date": incident_date,
                        "source_names": [],
                        "seed_urls": [],
                        "attack_tx_hashes": [],
                        "attack_type_raws": [],
                        "summary_candidates": [],
                        "note_candidates": [],
                        "date_range": {"first_seen": incident_date, "last_seen": incident_date},
                        "trigger_type": "historical_source_snapshot",
                        "seed_type": "historical_source_snapshot",
                        "loss_texts": [],
                    },
                )
                source_name = row.get("source_name", "").strip()
                source_url = row.get("source_url", "").strip()
                attack_type = row.get("attack_type_raw", "").strip() or row.get("attack_type_normalized", "").strip()
                summary = row.get("summary", "").strip()
                notes = row.get("notes", "").strip()
                attack_tx_url = row.get("attack_tx_url", "").strip()

                if source_name and source_name not in entry["source_names"]:
                    entry["source_names"].append(source_name)
                if source_url and source_url not in entry["seed_urls"]:
                    entry["seed_urls"].append(source_url)
                if attack_type and attack_type not in entry["attack_type_raws"]:
                    entry["attack_type_raws"].append(attack_type)
                if summary and summary not in entry["summary_candidates"]:
                    entry["summary_candidates"].append(summary)
                if notes and notes not in entry["note_candidates"]:
                    entry["note_candidates"].append(notes)
                if attack_tx_url:
                    tx_hash_match = re.search(r"(0x[a-fA-F0-9]{64})", attack_tx_url)
                    if tx_hash_match:
                        tx_hash = tx_hash_match.group(1)
                        if tx_hash not in entry["attack_tx_hashes"]:
                            entry["attack_tx_hashes"].append(tx_hash)
                loss_text = row.get("loss_text", "").strip()
                if loss_text and loss_text not in entry["loss_texts"]:
                    entry["loss_texts"].append(loss_text)
                if entry["chain"] == "Unknown":
                    entry["chain"] = row.get("chain", "").strip() or entry["chain"]

    items = list(grouped.values())
    for item in items:
        if not item["summary_candidates"]:
            item["summary_candidates"] = [
                f"{item['incident_name']} was collected automatically from historical security source snapshots."
            ]
        if not item["note_candidates"]:
            item["note_candidates"] = [
                "This is a source-derived incident lead collected from historical source snapshots."
            ]
    items.sort(key=lambda item: (item["incident_date"], item["incident_name"].lower()), reverse=True)
    return items

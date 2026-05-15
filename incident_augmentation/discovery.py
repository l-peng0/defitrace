from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

from incident_collector.collectors import COLLECTOR_REGISTRY
from incident_collector.collectors.base import CollectorConfig
from incident_collector.models import IncidentRecord
from incident_collector.utils import extract_urls


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_incident_id(name: str, chain: str, incident_date: str) -> str:
    value = "-".join(part for part in [name, chain, incident_date] if part)
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def extract_tx_hash(value: str) -> str:
    match = re.search(r"(0x[a-fA-F0-9]{64})", value)
    return match.group(1) if match else ""


@dataclass
class DiscoveredIncident:
    incident_key: str
    incident_name: str
    protocol_name: str
    chain: str
    attack_type_raws: set[str] = field(default_factory=set)
    source_names: set[str] = field(default_factory=set)
    source_urls: list[str] = field(default_factory=list)
    attack_tx_hashes: list[str] = field(default_factory=list)
    attack_contract_urls: list[str] = field(default_factory=list)
    victim_contract_urls: list[str] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    first_date: str = ""
    last_date: str = ""

    def absorb(self, record: IncidentRecord) -> None:
        self.protocol_name = self.protocol_name or record.project_name
        self.chain = self.chain or record.chain
        self.attack_type_raws.add(record.attack_type_raw)
        self.source_names.add(record.source_name)
        self.source_urls.extend(extract_urls(record.source_url, record.notes, record.summary))
        attack_tx_hash = extract_tx_hash(record.attack_tx_url)
        if attack_tx_hash:
            self.attack_tx_hashes.append(attack_tx_hash)
        if record.attack_contract_url:
            self.attack_contract_urls.append(record.attack_contract_url)
        if record.victim_contract_url:
            self.victim_contract_urls.append(record.victim_contract_url)
        if record.summary:
            self.summaries.append(record.summary)
        if record.notes:
            self.notes.append(record.notes)
        for tag in record.tags:
            if tag:
                self.tags.add(tag)
        date_iso = record.incident_date.isoformat()
        if not self.first_date or date_iso < self.first_date:
            self.first_date = date_iso
        if not self.last_date or date_iso > self.last_date:
            self.last_date = date_iso

    def to_seed_payload(self) -> dict:
        source_urls = list(dict.fromkeys(self.source_urls))
        incident_date = self.first_date or self.last_date
        return {
            "incident_id": build_incident_id(self.incident_name, self.chain, incident_date),
            "job_id": "",
            "trigger_type": "discovery_sync",
            "seed_type": "crawler_discovered_incident",
            "chain": self.chain or "unknown",
            "protocol_name": self.protocol_name,
            "incident_name": self.incident_name,
            "incident_date": incident_date,
            "attack_tx_hashes": list(dict.fromkeys(self.attack_tx_hashes)),
            "attacker_addresses": [],
            "seed_urls": source_urls,
            "tags": sorted(self.tags | {"discovered", "auto_collected"}),
            "created_at": "",
            "source_names": sorted(self.source_names),
            "attack_type_raws": sorted(value for value in self.attack_type_raws if value),
            "attack_contract_urls": list(dict.fromkeys(self.attack_contract_urls)),
            "victim_contract_urls": list(dict.fromkeys(self.victim_contract_urls)),
            "summary_candidates": self.summaries[:5],
            "note_candidates": self.notes[:5],
            "date_range": {
                "first_seen": self.first_date,
                "last_seen": self.last_date,
            },
        }


def collect_records(
    sources: Iterable[str],
    theme: str = "",
) -> list[IncidentRecord]:
    config = CollectorConfig(start_date=None, end_date=None, theme=theme)
    records: list[IncidentRecord] = []
    for name in sources:
        collector_cls = COLLECTOR_REGISTRY[name]
        collector = collector_cls(config)
        records.extend(collector.collect())
    records.sort(key=lambda record: (record.incident_date, record.source_name, record.project_name))
    return records


def group_records_to_incidents(records: Iterable[IncidentRecord]) -> list[DiscoveredIncident]:
    grouped: dict[str, DiscoveredIncident] = {}
    key_proto: dict[str, str] = {}  # key → normalized protocol name that owns it
    for record in records:
        if "price" not in (record.attack_type_raw + " " + record.attack_type_normalized + " " + " ".join(record.tags)).lower() and "manip" not in (record.attack_type_raw + " " + record.attack_type_normalized + " " + " ".join(record.tags)).lower():
            continue
        base_key = normalize_name(f"{record.project_name}-{record.chain}-{record.incident_date.isoformat()}")
        record_proto = normalize_name(record.project_name)
        # Detect collision: same normalized key, genuinely different protocol name
        if base_key in key_proto and key_proto[base_key] != record_proto:
            suffix = 2
            key = f"{base_key}_{suffix}"
            while key in key_proto and key_proto[key] != record_proto:
                suffix += 1
                key = f"{base_key}_{suffix}"
            if key not in grouped:
                logger.warning(
                    "discovery.key_collision",
                    extra={
                        "base_key": base_key,
                        "existing_protocol": key_proto[base_key],
                        "new_protocol": record.project_name,
                        "assigned_key": key,
                    },
                )
        else:
            key = base_key
        key_proto.setdefault(key, record_proto)
        incident = grouped.setdefault(
            key,
            DiscoveredIncident(
                incident_key=key,
                incident_name=record.project_name,
                protocol_name=record.project_name,
                chain=record.chain,
            ),
        )
        incident.absorb(record)
    return sorted(grouped.values(), key=lambda item: (item.first_date, item.incident_name.lower()))


def write_seed_payloads(
    incidents: Iterable[DiscoveredIncident], output_dir: str | Path
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for incident in incidents:
        payload = incident.to_seed_payload()
        path = output_path / f"{payload['incident_id']}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
        paths.append(path)
    return paths


def run_discovery_sync(
    sources: Iterable[str],
    seeds_dir: str | Path,
    runs_dir: str | Path,
    execute_augmentation: bool = True,
) -> dict:
    from .pipeline import run_augmentation_mvp

    sources_list = list(sources)  # materialise once — Iterable may be a one-shot generator
    records = collect_records(sources=sources_list, theme="price manipulation")
    incidents = group_records_to_incidents(records)
    seed_paths = write_seed_payloads(incidents, seeds_dir)

    run_dirs: list[str] = []
    if execute_augmentation:
        for seed_path in seed_paths:
            run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=runs_dir)
            run_dirs.append(str(run_dir))

    return {
        "source_count": len(sources_list),
        "record_count": len(records),
        "incident_count": len(incidents),
        "seed_paths": [str(path) for path in seed_paths],
        "run_dirs": run_dirs,
    }

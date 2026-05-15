from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class IncidentSeed:
    incident_id: str
    job_id: str
    trigger_type: str
    seed_type: str
    chain: str
    protocol_name: str = ""
    incident_name: str = ""
    incident_date: str = ""
    attack_tx_hashes: list[str] = field(default_factory=list)
    attacker_addresses: list[str] = field(default_factory=list)
    seed_urls: list[str] = field(default_factory=list)
    attack_contract_urls: list[str] = field(default_factory=list)
    victim_contract_urls: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)
    attack_type_raws: list[str] = field(default_factory=list)
    summary_candidates: list[str] = field(default_factory=list)
    note_candidates: list[str] = field(default_factory=list)
    date_range: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IncidentSeed":
        incident_id = str(payload.get("incident_id") or "")
        return cls(
            incident_id=incident_id,
            job_id=str(payload.get("job_id") or (f"{incident_id}-job" if incident_id else "")),
            trigger_type=str(payload.get("trigger_type") or "manual"),
            seed_type=str(payload.get("seed_type") or "unknown"),
            chain=str(payload.get("chain") or "unknown"),
            protocol_name=str(payload.get("protocol_name") or ""),
            incident_name=str(payload.get("incident_name") or ""),
            incident_date=str(payload.get("incident_date") or ""),
            attack_tx_hashes=[str(item) for item in payload.get("attack_tx_hashes", [])],
            attacker_addresses=[str(item) for item in payload.get("attacker_addresses", [])],
            seed_urls=[str(item) for item in payload.get("seed_urls", [])],
            attack_contract_urls=[str(item) for item in payload.get("attack_contract_urls", [])],
            victim_contract_urls=[str(item) for item in payload.get("victim_contract_urls", [])],
            tags=[str(item) for item in payload.get("tags", [])],
            source_names=[str(item) for item in payload.get("source_names", [])],
            attack_type_raws=[str(item) for item in payload.get("attack_type_raws", [])],
            summary_candidates=[str(item) for item in payload.get("summary_candidates", [])],
            note_candidates=[str(item) for item in payload.get("note_candidates", [])],
            date_range=dict(payload.get("date_range") or {}),
            created_at=str(payload.get("created_at") or utc_now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunState:
    job_id: str
    incident_id: str
    trigger_type: str
    current_stage: str
    node_status: dict[str, str]
    retry_counts: dict[str, int]
    started_at: str
    updated_at: str
    completed_at: str | None = None
    run_notes: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def for_seed(cls, seed: IncidentSeed) -> "RunState":
        now = utc_now_iso()
        return cls(
            job_id=seed.job_id,
            incident_id=seed.incident_id,
            trigger_type=seed.trigger_type,
            current_stage="seed_loaded",
            node_status={"seed_loader": "completed"},
            retry_counts={},
            started_at=now,
            updated_at=now,
        )

    def mark_stage(
        self,
        stage: str,
        status: str = "completed",
        note: str | None = None,
        artifact_name: str | None = None,
        artifact_path: str | None = None,
    ) -> None:
        self.current_stage = stage
        self.node_status[stage] = status
        self.updated_at = utc_now_iso()
        if note:
            self.run_notes.append(note)
        if artifact_name and artifact_path:
            self.artifacts[artifact_name] = artifact_path
        if status == "completed" and stage == "dashboard_projection":
            self.completed_at = self.updated_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

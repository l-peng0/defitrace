from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class IncidentRecord:
    incident_date: date
    source_name: str
    source_url: str
    project_name: str
    chain: str = ""
    attack_type_raw: str = ""
    attack_type_normalized: str = ""
    attack_tx_url: str = ""
    attack_contract_url: str = ""
    victim_contract_url: str = ""
    loss_text: str = ""
    summary: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, str]:
        row = asdict(self)
        row["incident_date"] = self.incident_date.isoformat()
        row["tags"] = "|".join(self.tags)
        return {key: str(value) for key, value in row.items()}


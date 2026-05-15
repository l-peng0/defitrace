from __future__ import annotations

import csv
from pathlib import Path

from incident_collector.models import IncidentRecord


FIELDNAMES = [
    "incident_date",
    "source_name",
    "source_url",
    "project_name",
    "chain",
    "attack_type_raw",
    "attack_type_normalized",
    "attack_tx_url",
    "attack_contract_url",
    "victim_contract_url",
    "loss_text",
    "summary",
    "notes",
    "tags",
]


def write_csv(records: list[IncidentRecord], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_row())


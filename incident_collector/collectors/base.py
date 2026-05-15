from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from incident_collector.models import IncidentRecord


@dataclass
class CollectorConfig:
    start_date: date | None = None
    end_date: date | None = None
    theme: str = ""


class BaseCollector:
    source_name = ""

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config

    def collect(self) -> list[IncidentRecord]:
        raise NotImplementedError


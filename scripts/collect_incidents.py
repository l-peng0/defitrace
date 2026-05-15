from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incident_collector.collectors import COLLECTOR_REGISTRY
from incident_collector.collectors.base import CollectorConfig
from incident_collector.exporters import write_csv
from incident_collector.models import IncidentRecord
from incident_collector.utils import parse_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect blockchain security incidents from multiple sources."
    )
    parser.add_argument(
        "--sources",
        default="slowmist,defihacklabs",
        help="Comma-separated collector names. Supported: slowmist,defihacklabs",
    )
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format")
    parser.add_argument(
        "--theme",
        default="",
        help="Optional task theme label, such as 'price manipulation'",
    )
    parser.add_argument(
        "--output",
        default="output/incidents.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print a short stdout summary after collection",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> CollectorConfig:
    start_date = parse_date(args.start_date) if args.start_date else None
    end_date = parse_date(args.end_date) if args.end_date else None
    return CollectorConfig(start_date=start_date, end_date=end_date, theme=args.theme)


def collect_all(args: argparse.Namespace) -> list[IncidentRecord]:
    config = build_config(args)
    names = [name.strip().lower() for name in args.sources.split(",") if name.strip()]
    records: list[IncidentRecord] = []

    for name in names:
        collector_cls = COLLECTOR_REGISTRY.get(name)
        if not collector_cls:
            raise SystemExit(f"Unsupported collector: {name}")
        collector = collector_cls(config)
        records.extend(collector.collect())

    records.sort(key=lambda record: (record.incident_date, record.source_name, record.project_name))
    return records


def main() -> int:
    args = parse_args()
    records = collect_all(args)
    write_csv(records, args.output)

    if args.print_summary:
        print(f"Collected {len(records)} records")
        for source_name in sorted({record.source_name for record in records}):
            count = sum(1 for record in records if record.source_name == source_name)
            print(f"- {source_name}: {count}")
        if records:
            print(f"- date range in output: {records[0].incident_date} to {records[-1].incident_date}")
        print(f"- csv: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

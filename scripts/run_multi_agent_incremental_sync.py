from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incident_augmentation.discovery import run_discovery_sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the automated full-history discovery sync and generate augmentation runs."
    )
    parser.add_argument(
        "--sources",
        default="slowmist,web3sec,external_explorer,defihacklabs",
        help="Comma-separated source list.",
    )
    parser.add_argument(
        "--seeds-dir",
        default="runs/discovery_seeds",
        help="Where discovered seed JSON files should be written.",
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Where augmentation run folders should be written.",
    )
    parser.add_argument(
        "--no-augment",
        action="store_true",
        help="Only discover and write seeds; do not execute augmentation runs.",
    )
    parser.add_argument(
        "--summary-output",
        default="runs/discovery_sync_summary.json",
        help="Where the sync summary JSON should be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = [name.strip().lower() for name in args.sources.split(",") if name.strip()]
    summary = run_discovery_sync(
        sources=sources,
        seeds_dir=args.seeds_dir,
        runs_dir=args.runs_dir,
        execute_augmentation=not args.no_augment,
    )
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

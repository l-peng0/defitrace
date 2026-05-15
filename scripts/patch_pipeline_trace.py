"""One-shot deploy patch: backfill pipeline_trace into live technical_analysis.json files.

This script is called from ssm-deploy.json after seed_fixtures.py runs.
It does a targeted force-overwrite of the pipeline_trace key (even if the live
file already has the key) using the fixture as the authoritative source.

Safe to run multiple times — idempotent if pipeline_trace already matches.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURE_RUNS = Path("/opt/capstone/app/data/fixtures/runs")
LIVE_RUNS = Path("/opt/capstone/data/runs")

# Map: fixture run dir name → live run dir name (if they differ)
# Add entries here for any run where the fixture name != the live run dir name.
PATCH_TARGETS: list[tuple[str, str]] = [
    # fixture name                                    live run dir name
    ("paribus-arbitrum-2025-01-18",                  "paribus-arbitrum-2025-01-18"),
    ("paribus-2025-01-18-price-manipulation-incident-arbitrum",
                                                     "paribus-2025-01-18-price-manipulation-incident-arbitrum"),
    ("bgm-2024-11-10-price-manipulation-incident-bsc",
                                                     "bgm-2024-11-10-price-manipulation-incident-bsc"),
]


def patch_run(fixture_run: Path, live_run: Path) -> None:
    fixture_ta = fixture_run / "technical_analysis.json"
    live_ta = live_run / "technical_analysis.json"
    if not fixture_ta.exists():
        print(f"[patch] fixture not found: {fixture_ta}, skipping")
        return
    if not live_ta.exists():
        print(f"[patch] live file not found: {live_ta}, skipping")
        return

    fdata = json.loads(fixture_ta.read_text())
    ldata = json.loads(live_ta.read_text())

    pt = fdata.get("pipeline_trace")
    if not pt or not pt.get("records"):
        print(f"[patch] fixture pipeline_trace empty for {fixture_run.name}, skipping")
        return

    live_pt = ldata.get("pipeline_trace")
    live_count = len(live_pt.get("records", [])) if isinstance(live_pt, dict) else 0
    fixture_count = len(pt.get("records", []))

    if live_count >= fixture_count:
        print(f"[patch] {live_run.name}: already has {live_count} records, no update needed")
        return

    ldata["pipeline_trace"] = pt
    live_ta.write_text(json.dumps(ldata, indent=2, ensure_ascii=True) + "\n")
    print(f"[patch] {live_run.name}: pipeline_trace backfilled ({live_count} → {fixture_count} records)")


def main() -> None:
    if not FIXTURE_RUNS.exists():
        print(f"[patch] fixture_runs not found: {FIXTURE_RUNS}")
        return
    if not LIVE_RUNS.exists():
        print(f"[patch] live_runs not found: {LIVE_RUNS}")
        return

    for fixture_name, live_name in PATCH_TARGETS:
        fixture_run = FIXTURE_RUNS / fixture_name
        live_run = LIVE_RUNS / live_name
        patch_run(fixture_run, live_run)

    print("[patch] done")


if __name__ == "__main__":
    main()

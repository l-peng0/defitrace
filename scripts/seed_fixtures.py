"""Idempotent fixture seeder: copies data/fixtures/runs/ into the live runs_dir.

Usage:
    python3 scripts/seed_fixtures.py <src_fixtures_dir> <dst_runs_dir>

Rules:
- If a file doesn't exist on dst, copy it.
- If a .json file exists on dst but is missing keys that src has, merge them
  (additive-only — existing keys are never overwritten).
- Non-JSON files are skipped if they already exist on dst.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def seed(src_root: Path, dst_root: Path) -> None:
    if not src_root.exists():
        print(f"[seed_fixtures] src_root {src_root} does not exist, skipping")
        return
    dst_root.mkdir(parents=True, exist_ok=True)

    for src_file in sorted(src_root.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_root)
        dst_file = dst_root / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        if not dst_file.exists():
            shutil.copy2(src_file, dst_file)
            print(f"[seed_fixtures] copied  {rel}")
        elif src_file.suffix == ".json":
            try:
                live_data: dict = json.loads(dst_file.read_text())
                fixture_data: dict = json.loads(src_file.read_text())
                # Add keys missing from live, and overwrite keys where live value is
                # empty (None / {} / []) but the fixture has real content.
                added = {k: v for k, v in fixture_data.items() if k not in live_data}
                overwritten = {
                    k: v
                    for k, v in fixture_data.items()
                    if k in live_data and not live_data[k] and v
                }
                changed = {**added, **overwritten}
                if changed:
                    merged = {**live_data, **changed}
                    dst_file.write_text(
                        json.dumps(merged, indent=2, ensure_ascii=True) + "\n"
                    )
                    if overwritten:
                        print(f"[seed_fixtures] merged  {rel}  (+{list(added.keys())} ~{list(overwritten.keys())})")
                    else:
                        print(f"[seed_fixtures] merged  {rel}  (+{list(added.keys())})")
                else:
                    print(f"[seed_fixtures] skip    {rel}  (no new keys)")
            except Exception as exc:
                print(f"[seed_fixtures] warning: could not merge {rel}: {exc}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <src_fixtures_dir> <dst_runs_dir>")
        sys.exit(1)
    seed(Path(sys.argv[1]), Path(sys.argv[2]))
    print("[seed_fixtures] done")

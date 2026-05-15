from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


def _seed_fixture_files(runs_dir: Path) -> None:
    """Copy fixture runs into the persistent runs_dir, file-by-file (idempotent).

    Only copies files that do not already exist on disk, so live run data is
    never overwritten.  If a fixture file IS newer than the on-disk copy AND
    the on-disk copy lacks a key that the fixture has (e.g. pipeline_trace),
    the fixture file wins — this lets us backfill synthetic fields safely.
    """
    fixture_runs = ROOT / "data" / "fixtures" / "runs"
    if not fixture_runs.exists():
        return
    runs_dir.mkdir(parents=True, exist_ok=True)
    for src_run in fixture_runs.iterdir():
        if not src_run.is_dir() or src_run.name.startswith("_"):
            continue
        dst_run = runs_dir / src_run.name
        dst_run.mkdir(parents=True, exist_ok=True)
        for src_file in src_run.iterdir():
            if not src_file.is_file():
                continue
            dst_file = dst_run / src_file.name
            if not dst_file.exists():
                shutil.copy2(src_file, dst_file)
                logger.info("seeded fixture file %s", dst_file)
            elif src_file.suffix == ".json":
                # Merge: if the fixture JSON has keys missing from the on-disk
                # copy, write a merged version so synthetic fields (like
                # pipeline_trace) are backfilled without losing live data.
                try:
                    live_data = json.loads(dst_file.read_text())
                    fixture_data = json.loads(src_file.read_text())
                    added = {k: v for k, v in fixture_data.items() if k not in live_data}
                    # Also overwrite keys where live value is empty ({},[],None,"")
                    # but the fixture has real content — e.g. pipeline_trace: {}.
                    overwritten = {
                        k: v
                        for k, v in fixture_data.items()
                        if k in live_data and not live_data[k] and v
                    }
                    changed = {**added, **overwritten}
                    if changed:
                        merged = {**live_data, **changed}
                        dst_file.write_text(json.dumps(merged, indent=2, ensure_ascii=True) + "\n")
                        logger.info("backfilled keys %s (overwrote empty: %s) into %s", list(added.keys()), list(overwritten.keys()), dst_file)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("could not merge fixture %s: %s", src_file, exc)


def main() -> None:
    runs_dir_env = os.environ.get("CAPSTONE_RUNS_DIR", str(ROOT / "runs"))
    _seed_fixture_files(Path(runs_dir_env))

    uvicorn.run(
        "backend.app:app",
        host=os.environ.get("CAPSTONE_BIND_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", os.environ.get("CAPSTONE_PORT", "8000"))),
        reload=False,
    )


if __name__ == "__main__":
    main()

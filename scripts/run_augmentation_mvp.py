from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incident_augmentation import run_augmentation_mvp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the capstone data augmentation MVP from one incident seed JSON."
    )
    parser.add_argument(
        "--seed",
        required=True,
        help="Path to the incident_seed.json input file.",
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Directory where run folders should be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = run_augmentation_mvp(seed_path=args.seed, runs_dir=args.runs_dir)
    print(f"MVP run completed: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

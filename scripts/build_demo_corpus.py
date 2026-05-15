from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incident_augmentation.demo_corpus import build_demo_corpus


def main() -> int:
    summary = build_demo_corpus(
        sample_targets_path=ROOT / "examples" / "sample_source_expansion_targets.json",
        runs_dir=ROOT / "runs",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

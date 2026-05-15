from __future__ import annotations

import json
import re
from pathlib import Path

from .pipeline import run_augmentation_mvp


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_demo_corpus(sample_targets_path: str | Path, runs_dir: str | Path) -> dict:
    sample_targets = json.loads(Path(sample_targets_path).read_text())
    runs_dir_path = Path(runs_dir)
    built_runs: list[str] = []
    queue_dir = runs_dir_path / "_demo_seed_inputs"
    queue_dir.mkdir(parents=True, exist_ok=True)

    for item in sample_targets:
        incident_id = slugify("-".join([item["incident_name"], item.get("chain", ""), item.get("incident_date", "")]))
        seed = {
            "incident_id": incident_id,
            "job_id": f"{incident_id}-demo-job",
            "trigger_type": "demo_corpus",
            "seed_type": "sample_source_expansion_target",
            "chain": item.get("chain", "unknown"),
            "protocol_name": item["incident_name"],
            "incident_name": item["incident_name"],
            "incident_date": item.get("incident_date", ""),
            "seed_urls": item.get("seed_urls", []),
            "tags": [item.get("attack_type", ""), "demo_corpus", "source_expansion_target"],
            "attack_type_raws": [item.get("attack_type", "")],
            "summary_candidates": [item.get("goal", "")],
            "source_names": ["sample_target_pack"],
        }
        seed_path = queue_dir / f"{incident_id}.json"
        seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=True) + "\n")
        run_dir = run_augmentation_mvp(seed_path=seed_path, runs_dir=runs_dir_path)
        built_runs.append(str(run_dir))

    summary = {"run_count": len(built_runs), "runs": built_runs}
    summary_path = queue_dir / "demo_corpus_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    return summary

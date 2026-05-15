"""Batch-run the strict 14-case price-manipulation catalog through the pipeline.

Usage:
  .venv/bin/python scripts/batch_run_sheet_cases.py                        # dry-run (no LLM)
  .venv/bin/python scripts/batch_run_sheet_cases.py --run --limit 2        # run first 2 cases
  .venv/bin/python scripts/batch_run_sheet_cases.py --run --ids paribus-arbitrum-2025-01-18,bgm-bsc-2024-11-10
  .venv/bin/python scripts/batch_run_sheet_cases.py --run --concurrency 2  # parallel
  .venv/bin/python scripts/batch_run_sheet_cases.py --run --only-missing   # skip completed runs
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CATALOG = ROOT / "data" / "incident_catalog_strict_pm14.csv"
SEEDS_DIR = ROOT / "data" / "fixtures" / "seeds"
RUNS_DIR = ROOT / "data" / "fixtures" / "runs"
REPORT_DIR = ROOT / "data" / "fixtures" / "_batch_reports"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def row_to_seed(row: dict) -> dict:
    """Convert a catalog row to an IncidentSeed-compatible dict."""
    chain_label = {
        "ethereum": "Ethereum", "bsc": "BSC",
        "arbitrum": "Arbitrum", "base": "Base",
    }.get(row["chain"], row["chain"].title())

    seed_urls = [u.strip() for u in row["source_urls"].split("|") if u.strip()]
    attack_contract_urls = [u.strip() for u in row.get("attack_contract_urls", "").split("|") if u.strip()]
    victim_contract_urls = [u.strip() for u in row.get("victim_contract_urls", "").split("|") if u.strip()]
    attacker_addresses = [row["attacker_address"]] if row.get("attacker_address") else []
    attack_contract_addresses = [row["attack_contract_address"]] if row.get("attack_contract_address") else []

    return {
        "incident_id": row["incident_id"],
        "job_id": f"{row['incident_id']}-batch",
        "trigger_type": "batch",
        "seed_type": "tx_hash",
        "chain": chain_label,
        "protocol_name": row["protocol"].title(),
        "incident_name": f"{row['protocol'].title()} {row['date']} price-manipulation incident",
        "incident_date": row["date"],
        "attack_tx_hashes": [row["attack_tx_hash"]] if row["attack_tx_hash"] else [],
        "attacker_addresses": attacker_addresses or attack_contract_addresses,
        "attack_contract_urls": attack_contract_urls,
        "victim_contract_urls": victim_contract_urls,
        "seed_urls": seed_urls,
        "summary_candidates": [row["note_first_sentence"]] if row["note_first_sentence"] else [],
        "tags": ["strict_price_manipulation", "price_manipulation", row["chain"], "defi"],
        "created_at": utc_now_iso(),
    }


def write_seed(seed: dict) -> Path:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    path = SEEDS_DIR / f"{seed['incident_id']}.json"
    path.write_text(json.dumps(seed, indent=2))
    return path


def run_one(row: dict, do_run: bool, only_missing: bool) -> dict:
    incident_id = row["incident_id"]
    started = time.perf_counter()
    result: dict = {"incident_id": incident_id, "started_at": utc_now_iso()}
    try:
        existing_run_dir = RUNS_DIR / incident_id
        if only_missing and existing_run_dir.exists():
            result.update(status="skipped", reason="existing run output found", run_dir=str(existing_run_dir))
            return result

        seed = row_to_seed(row)
        if not seed["attack_tx_hashes"]:
            result.update(status="skipped", reason="no tx hash extracted from sheet")
            return result
        seed_path = write_seed(seed)
        result["seed_path"] = str(seed_path)

        if not do_run:
            result.update(status="dry_run", reason="--run not specified")
            return result

        from incident_augmentation.pipeline import run_augmentation_mvp
        run_dir = run_augmentation_mvp(seed_path, runs_dir=RUNS_DIR)
        ta_path = Path(run_dir) / "technical_analysis.json"
        ta = json.loads(ta_path.read_text()) if ta_path.exists() else {}
        pt = ta.get("pipeline_trace") or {}
        qa_retry_triggered = pt.get("qa_retry_triggered", False)
        # Completeness score lives in quality_report.json (v2 if retry fired)
        qr_path = (
            Path(run_dir) / "qa_retry" / "quality_report_v2.json"
            if qa_retry_triggered
            else Path(run_dir) / "quality_report.json"
        )
        completeness = None
        if qr_path.exists():
            completeness = json.loads(qr_path.read_text()).get("completeness_score")
        result.update(
            status="completed",
            run_dir=str(run_dir),
            completeness_score=completeness,
            qa_retry_triggered=qa_retry_triggered,
            revision_round=ta.get("revision_round"),
        )
    except Exception as exc:
        result.update(
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc().splitlines()[-6:],
        )
    finally:
        result["duration_s"] = round(time.perf_counter() - started, 1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Actually invoke the pipeline (consumes LLM tokens). Without this, performs a dry-run only.")
    parser.add_argument("--limit", type=int, default=0, help="Run at most N cases (0 = all).")
    parser.add_argument("--ids", default="", help="Comma-separated incident_ids to run (overrides --limit).")
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel workers (default 1).")
    parser.add_argument("--catalog", default=str(CATALOG))
    parser.add_argument("--only-missing", action="store_true", help="Skip cases that already have a run directory.")
    parser.add_argument("--start-date", default="", help="Keep rows on or after YYYY-MM-DD.")
    parser.add_argument("--end-date", default="", help="Keep rows on or before YYYY-MM-DD.")
    args = parser.parse_args()

    if not Path(args.catalog).exists():
        print(f"ERR: catalog not found: {args.catalog}")
        return 1

    rows = list(csv.DictReader(Path(args.catalog).open()))
    if args.start_date:
        rows = [r for r in rows if r.get("date", "") >= args.start_date]
    if args.end_date:
        rows = [r for r in rows if r.get("date", "") <= args.end_date]
    if args.ids:
        keep = {x.strip() for x in args.ids.split(",") if x.strip()}
        rows = [r for r in rows if r["incident_id"] in keep]
    elif args.limit > 0:
        rows = rows[: args.limit]

    print(f"=== Strict PM batch run: {len(rows)} cases | run={args.run} | concurrency={args.concurrency} | only_missing={args.only_missing} ===")
    for r in rows:
        print(f"  - {r['incident_id']}  tx={r['attack_tx_hash'][:14]}…  chain={r['chain']}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"batch-{int(time.time())}.json"
    results: list[dict] = []
    t0 = time.perf_counter()

    if args.concurrency <= 1:
        for r in rows:
            res = run_one(r, args.run, args.only_missing)
            print(f"  [{res['status'].upper():9}] {res['incident_id']:60} {res.get('duration_s', '?')}s {res.get('error', '')[:80]}")
            results.append(res)
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(run_one, r, args.run, args.only_missing): r for r in rows}
            for fut in as_completed(futures):
                res = fut.result()
                print(f"  [{res['status'].upper():9}] {res['incident_id']:60} {res.get('duration_s', '?')}s {res.get('error', '')[:80]}")
                results.append(res)

    summary = {
        "total": len(results),
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "dry_run": sum(1 for r in results if r["status"] == "dry_run"),
        "qa_retry_triggered": sum(1 for r in results if r.get("qa_retry_triggered")),
        "wall_time_s": round(time.perf_counter() - t0, 1),
    }
    payload = {"summary": summary, "results": results, "ran_at": utc_now_iso()}
    report_path.write_text(json.dumps(payload, indent=2))
    print()
    print(json.dumps(summary, indent=2))
    print(f"\nReport -> {report_path}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

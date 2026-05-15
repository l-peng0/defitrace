from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path("/Users/lauren/Desktop/2026spring/capstone")
FINAL_OUTPUT = ROOT / "output" / "final"

SOURCE = FINAL_OUTPUT / "shared_sheet_delivery_review.csv"
COMPLETE = FINAL_OUTPUT / "shared_sheet_delivery_complete.csv"
HOLDOUT = FINAL_OUTPUT / "shared_sheet_delivery_holdout.csv"

FINAL_HEADERS = [
    "time (format: yyyy-mm-dd)",
    "data resouce (all resources you referenced)",
    "blockchain platform",
    "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)",
    "attack contract address (via explorer link)",
    "victim contract address (via explorer link)",
    "note (you can give note for special cases, or just copy report content)",
]

CRITICAL_HEADERS = [
    "time (format: yyyy-mm-dd)",
    "data resouce (all resources you referenced)",
    "blockchain platform",
    "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)",
    "attack contract address (via explorer link)",
    "victim contract address (via explorer link)",
    "note (you can give note for special cases, or just copy report content)",
]


def main() -> int:
    with SOURCE.open() as handle:
        rows = list(csv.DictReader(handle))

    complete_rows = []
    holdout_rows = []
    holdout_fields = FINAL_HEADERS + ["project_name", "attack_type_raw", "poc_url", "missing_fields"]

    for row in rows:
        missing = [header for header in CRITICAL_HEADERS if not row.get(header, "").strip()]
        if missing:
            row = dict(row)
            row["missing_fields"] = "; ".join(missing)
            holdout_rows.append(row)
        else:
            complete_rows.append({header: row[header] for header in FINAL_HEADERS})

    with COMPLETE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_HEADERS)
        writer.writeheader()
        writer.writerows(complete_rows)

    with HOLDOUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=holdout_fields)
        writer.writeheader()
        writer.writerows(holdout_rows)

    print(f"complete={len(complete_rows)} holdout={len(holdout_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

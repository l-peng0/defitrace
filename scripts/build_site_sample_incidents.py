from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "output" / "final" / "shared_sheet_delivery_review.csv"
TARGET_JSON = ROOT / "site" / "data" / "sample_incidents.json"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def label_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "web3sec" in host:
        return "Web3Sec"
    if "github.com" in host:
        return "PoC / GitHub"
    if "x.com" in host or "twitter.com" in host:
        return "X / Twitter"
    if "certik.com" in host:
        return "CertiK"
    if "slowmist" in host:
        return "SlowMist"
    if "bscscan.com" in host or "etherscan.io" in host or "arbiscan.io" in host or "basescan.org" in host:
        return "Explorer"
    if "bitfinding.com" in host:
        return "BitFinding"
    if "verichains.io" in host:
        return "Verichains"
    if "quillaudits.com" in host:
        return "QuillAudits"
    if "quadrigainitiative.com" in host:
        return "Quadriga Initiative"
    return host or "Source"


def main() -> int:
    rows = list(csv.DictReader(SOURCE_CSV.open()))
    incidents: list[dict] = []

    for row in rows:
        resources = [item.strip() for item in row["data resouce (all resources you referenced)"].splitlines() if item.strip()]
        incidents.append(
            {
                "incident_id": slugify(row["project_name"]),
                "project_name": row["project_name"],
                "incident_date": row["time (format: yyyy-mm-dd)"],
                "chain": row["blockchain platform"],
                "attack_type": row["attack_type_raw"],
                "summary": row["note (you can give note for special cases, or just copy report content)"],
                "attack_tx_url": row["attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)"],
                "attack_contract_url": row["attack contract address (via explorer link)"],
                "victim_contract_url": row["victim contract address (via explorer link)"],
                "poc_url": row["poc_url"],
                "sources": [{"label": label_for_url(url), "url": url} for url in resources],
            }
        )

    incidents.sort(key=lambda item: item["incident_date"], reverse=True)
    TARGET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TARGET_JSON.write_text(json.dumps({"incidents": incidents}, indent=2, ensure_ascii=True) + "\n")
    print(f"Wrote {len(incidents)} sample incidents to {TARGET_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the curated 14-case strict price-manipulation catalog from the shared sheet.

Drops rows 13, 15, 17 (1-indexed) which are access-control / token-logic rather than classic price manipulation.
Output: data/incident_catalog_strict_pm14.csv with normalized columns the batch runner consumes.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "output" / "final" / "shared_sheet_delivery_final.csv"
DST = ROOT / "data" / "incident_catalog_strict_pm14.csv"

DROP_INDICES = {13, 15, 17}  # 1-indexed in the sheet
TX_RE = re.compile(r"0x[a-fA-F0-9]{64}")
ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")

CHAIN_ALIAS = {
    "Ethereum": "ethereum",
    "BSC": "bsc",
    "Arbitrum": "arbitrum",
    "Base": "base",
}


def slugify_protocol(note: str) -> str:
    """Pull a likely protocol name out of the note's first sentence."""
    first = note.split(".")[0].strip()
    m = re.search(r"against (?:an? |the )?([A-Z][A-Za-z0-9_]+)", first)
    if m:
        return m.group(1).lower()
    m = re.search(r"involving the ([A-Za-z0-9_]+)", first)
    if m:
        return m.group(1).lower()
    return "unknown"


def main() -> int:
    if not SRC.exists():
        print(f"ERR: missing {SRC}")
        return 1

    rows = list(csv.DictReader(SRC.open()))
    out_rows = []
    for i, r in enumerate(rows, 1):
        if i in DROP_INDICES:
            continue
        date = r["time (format: yyyy-mm-dd)"].strip()
        chain_label = r["blockchain platform"].strip()
        chain = CHAIN_ALIAS.get(chain_label, chain_label.lower())
        tx_match = TX_RE.search(r.get("attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)", ""))
        attack_contract_cell = r.get("attack contract address (via explorer link)", "")
        victim_contract_cell = r.get("victim contract address (via explorer link)", "")
        attack_addr_match = ADDR_RE.search(attack_contract_cell)
        victim_addr_match = ADDR_RE.search(victim_contract_cell)
        note = r.get("note (you can give note for special cases, or just copy report content)", "")
        protocol = slugify_protocol(note)
        incident_id = f"{protocol}-{chain}-{date}"
        out_rows.append({
            "incident_id": incident_id,
            "date": date,
            "chain": chain,
            "protocol": protocol,
            "attack_tx_hash": tx_match.group() if tx_match else "",
            "attacker_address": attack_addr_match.group() if attack_addr_match else "",
            "victim_address": victim_addr_match.group() if victim_addr_match else "",
            "attack_contract_address": attack_addr_match.group() if attack_addr_match else "",
            "victim_contract_address": victim_addr_match.group() if victim_addr_match else "",
            "attack_contract_urls": attack_contract_cell.replace("\n", " | "),
            "victim_contract_urls": victim_contract_cell.replace("\n", " | "),
            "source_urls": r.get("data resouce (all resources you referenced)", "").replace("\n", " | "),
            "note_first_sentence": note.split(".")[0][:200],
        })

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"Wrote {len(out_rows)} rows -> {DST}")
    for r in out_rows:
        print(f"  {r['incident_id']:60} tx={r['attack_tx_hash'][:14]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

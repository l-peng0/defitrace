from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path("/Users/lauren/Desktop/2026spring/capstone")
OUTPUT = ROOT / "output"


def read_rows(name: str) -> list[dict[str, str]]:
    path = OUTPUT / name
    with path.open() as handle:
        return list(csv.DictReader(handle))


def write_rows(name: str, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path = OUTPUT / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def poc_url_from_notes(notes: str) -> str:
    match = re.search(r"POC: (https?://\S+)", notes)
    return match.group(1) if match else ""


def build_sheet_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    slowmist = read_rows("slowmist_strict_pm.csv")
    web3sec = read_rows("web3sec_strict_pm.csv")
    external_explorer_all = read_rows("external_explorer_2024-09_to_2025-02_all.csv")

    price_related_external_explorer = {
        row["project_name"].strip().lower(): row
        for row in external_explorer_all
        if any(term in row["attack_type_raw"].lower() for term in ["price", "slippage"])
    }

    slowmist_by_name = {
        row["project_name"].strip().lower(): row
        for row in slowmist
    }

    sheet_rows: list[dict[str, str]] = []
    supporting_rows: list[dict[str, str]] = []

    for row in web3sec:
        project_key = row["project_name"].strip().lower()
        resources = [row["source_url"]]
        poc_url = poc_url_from_notes(row["notes"])
        if poc_url:
            resources.append(poc_url)
            supporting_rows.append(
                {
                    "incident_date": row["incident_date"],
                    "project_name": row["project_name"],
                    "source_name": "DeFiHackLabs",
                    "poc_url": poc_url,
                    "paired_source": "Web3Sec Notion",
                    "attack_type_raw": row["attack_type_raw"],
                }
            )

        if project_key in price_related_external_explorer:
            resources.append(price_related_external_explorer[project_key]["source_url"])

        if project_key in slowmist_by_name:
            resources.append(slowmist_by_name[project_key]["source_url"])

        sheet_rows.append(
            {
                "time (format: yyyy-mm-dd)": row["incident_date"],
                "data resouce (all resources you referenced)": "\n".join(dict.fromkeys(resources)),
                "blockchain platform": row["chain"],
                "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)": row["attack_tx_url"],
                "attack contract address (via explorer link)": row["attack_contract_url"],
                "victim contract address (via explorer link)": row["victim_contract_url"],
                "note (you can give note for special cases, or just copy report content)": row["summary"],
                "source_name": row["source_name"],
                "project_name": row["project_name"],
                "attack_type_raw": row["attack_type_raw"],
            }
        )

    for row in slowmist:
        project_key = row["project_name"].strip().lower()
        if any(existing["project_name"].strip().lower() == project_key for existing in sheet_rows):
            continue

        resources = [row["source_url"]]
        if project_key in price_related_external_explorer:
            resources.append(price_related_external_explorer[project_key]["source_url"])

        sheet_rows.append(
            {
                "time (format: yyyy-mm-dd)": row["incident_date"],
                "data resouce (all resources you referenced)": "\n".join(dict.fromkeys(resources)),
                "blockchain platform": row["chain"],
                "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)": row["attack_tx_url"] or row["source_url"],
                "attack contract address (via explorer link)": row["attack_contract_url"],
                "victim contract address (via explorer link)": row["victim_contract_url"],
                "note (you can give note for special cases, or just copy report content)": row["summary"],
                "source_name": row["source_name"],
                "project_name": row["project_name"],
                "attack_type_raw": row["attack_type_raw"],
            }
        )

    sheet_rows.sort(key=lambda item: (item["time (format: yyyy-mm-dd)"], item["project_name"]))
    supporting_rows.sort(key=lambda item: (item["incident_date"], item["project_name"]))
    return sheet_rows, supporting_rows


def main() -> int:
    sheet_rows, supporting_rows = build_sheet_rows()
    write_rows(
        "strict_pm_first_pass_sheet_ready.csv",
        [
            "time (format: yyyy-mm-dd)",
            "data resouce (all resources you referenced)",
            "blockchain platform",
            "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)",
            "attack contract address (via explorer link)",
            "victim contract address (via explorer link)",
            "note (you can give note for special cases, or just copy report content)",
            "source_name",
            "project_name",
            "attack_type_raw",
        ],
        sheet_rows,
    )
    write_rows(
        "defihacklabs_supporting_strict_pm.csv",
        [
            "incident_date",
            "project_name",
            "source_name",
            "poc_url",
            "paired_source",
            "attack_type_raw",
        ],
        supporting_rows,
    )
    print(f"sheet rows: {len(sheet_rows)}")
    print(f"defihacklabs supporting rows: {len(supporting_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

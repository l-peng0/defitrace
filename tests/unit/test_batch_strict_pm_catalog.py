from __future__ import annotations

import csv
from pathlib import Path

from incident_augmentation.models import IncidentSeed
from scripts.batch_run_sheet_cases import CATALOG, row_to_seed


def test_default_catalog_is_strict_pm14() -> None:
    rows = list(csv.DictReader(Path(CATALOG).open()))

    assert len(rows) == 14


def test_row_to_seed_preserves_strict_pm_fields() -> None:
    row = {
        "incident_id": "demo-ethereum-2024-09-26",
        "date": "2024-09-26",
        "chain": "ethereum",
        "protocol": "demo",
        "attack_tx_hash": "0x" + "a" * 64,
        "attacker_address": "",
        "victim_address": "0x" + "b" * 40,
        "attack_contract_address": "0x" + "c" * 40,
        "victim_contract_address": "0x" + "d" * 40,
        "attack_contract_urls": "https://etherscan.io/address/0x" + "c" * 40,
        "victim_contract_urls": "https://etherscan.io/address/0x" + "d" * 40,
        "source_urls": "https://example.com/postmortem | https://example.com/poc",
        "note_first_sentence": "A strict price manipulation case.",
    }

    seed = IncidentSeed.from_dict(row_to_seed(row))

    assert seed.attack_tx_hashes == [row["attack_tx_hash"]]
    assert seed.attacker_addresses == [row["attack_contract_address"]]
    assert seed.attack_contract_urls == [row["attack_contract_urls"]]
    assert seed.victim_contract_urls == [row["victim_contract_urls"]]
    assert "strict_price_manipulation" in seed.tags

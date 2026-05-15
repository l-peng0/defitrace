from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_list_incidents_merges_historical_source_snapshot_entries(tmp_db: Path, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_csv(
        repo_root / "data" / "history_snapshots" / "web3sec_strict_pm.csv",
        """incident_date,source_name,source_url,project_name,chain,attack_type_raw,attack_type_normalized,attack_tx_url,attack_contract_url,victim_contract_url,loss_text,summary,notes,tags
2025-01-18,Web3Sec Notion,https://example.com/paribus,Paribus,Arbitrum,Price Manipulation,price_manipulation,,,,$100k,Paribus summary,Paribus notes,price_manipulation
2025-01-10,Web3Sec Notion,https://example.com/fortunewheel,FortuneWheel,BSC,Price Manipulation,price_manipulation,,,,$20k,FortuneWheel summary,FortuneWheel notes,price_manipulation
""",
    )
    _write_csv(
        repo_root / "data" / "history_snapshots" / "slowmist_strict_pm.csv",
        """incident_date,source_name,source_url,project_name,chain,attack_type_raw,attack_type_normalized,attack_tx_url,attack_contract_url,victim_contract_url,loss_text,summary,notes,tags
2025-01-18,SlowMist,https://example.com/paribus-slowmist,Paribus,Arbitrum,Price Manipulation,price_manipulation,,,,$100k,Paribus slowmist summary,Paribus slowmist notes,price_manipulation
""",
    )
    _write_csv(
        repo_root / "data" / "history_snapshots" / "external_explorer_strict_pm.csv",
        "incident_date,source_name,source_url,project_name,chain,attack_type_raw,attack_type_normalized,attack_tx_url,attack_contract_url,victim_contract_url,loss_text,summary,notes,tags\n",
    )

    with patch("backend.database.settings") as db_settings, patch("backend.service.settings") as svc_settings, patch("backend.service.REPO_ROOT", repo_root):
        db_settings.database_path = tmp_db
        svc_settings.database_path = tmp_db
        svc_settings.runs_dir = tmp_path / "runs"

        from backend.service import JobManager

        incidents = JobManager().list_incidents()

    assert len(incidents) == 2
    assert incidents[0]["title"] == "Paribus"
    assert incidents[0]["status"] == "auto_collected_lead"
    assert incidents[0]["source_count"] == 2
    assert incidents[1]["title"] == "FortuneWheel"

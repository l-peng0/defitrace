from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _write_bundle(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "incident_library_entry.json").write_text(
        json.dumps(
            {
                "incident_id": "paribus-arbitrum-2025-01-18",
                "title": "Paribus",
                "protocol_name": "Paribus",
                "chain": "Arbitrum",
                "incident_date": "2025-01-18",
                "summary": "Old seed text should not be the final public report.",
                "status": "demo_live_dossier",
                "completeness_score": 85,
                "source_count": 4,
                "direct_source_count": 4,
                "secondary_source_count": 0,
                "social_count": 1,
                "poc_count": 1,
                "explorer_count": 0,
                "report_count": 2,
                "missing_fields": [],
                "last_updated": "2026-04-03T00:00:00+00:00",
                "pattern_label": "price_manipulation",
                "attack_tx_hashes": [
                    "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                    "0xf5e753d3da60db214f2261343c1e1bc46e674d2fa4b7a953eaf3c52123aeebd2",
                ],
                "source_preview": [],
            }
        )
    )
    (run_dir / "augmented_incident.json").write_text(
        json.dumps(
            {
                "incident_id": "paribus-arbitrum-2025-01-18",
                "title": "Paribus",
                "incident_date": "2025-01-18",
                "chain": "Arbitrum",
                "protocol_name": "Paribus",
                "summary": "Old seed text should not be the final public report.",
                "key_transactions": [
                    "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                    "0xf5e753d3da60db214f2261343c1e1bc46e674d2fa4b7a953eaf3c52123aeebd2",
                ],
                "key_addresses": [
                    "0x56190CAC88b8D4b5D5Ed668ef81828913932e7Ed",
                ],
                "timeline": [],
                "attacker_profile": {"recent_activity_summary": "Wallet cluster identified."},
                "pattern_hypotheses": [{"label": "price_manipulation"}],
                "source_summary": {"source_count": 4},
                "quality_report": {"completeness_score": 85, "missing_fields": []},
            }
        )
    )
    (run_dir / "quality_report.json").write_text(
        json.dumps({"completeness_score": 85, "missing_fields": ["funding_path"], "judge_summary": "Needs analyst polish."})
    )
    (run_dir / "source_index.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "src-001",
                        "url": "https://web3sec.notion.site/c582b99cd7a84be48d972ca2126a2a1f?v=4671590619bd4b2ab16a15256e4fbba1",
                        "source_type": "report",
                        "depth": 0,
                        "discovered_from": "incident_seed",
                        "fetch_status": "fetched",
                    },
                    {
                        "source_id": "src-002",
                        "url": "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2025-01/Paribus_exp.sol",
                        "source_type": "poc",
                        "depth": 0,
                        "discovered_from": "incident_seed",
                        "fetch_status": "fetched",
                    },
                    {
                        "source_id": "src-003",
                        "url": "https://bitfinding.com/blog/paribus-hack-interception",
                        "source_type": "report",
                        "depth": 0,
                        "discovered_from": "incident_seed",
                        "fetch_status": "fetched",
                    },
                    {
                        "source_id": "src-004",
                        "url": "https://x.com/BitFinding/status/1882880682512527516",
                        "source_type": "social",
                        "depth": 0,
                        "discovered_from": "incident_seed",
                        "fetch_status": "fetched",
                    },
                ]
            }
        )
    )
    (run_dir / "technical_analysis.json").write_text(
        json.dumps(
            {
                "incident_id": "paribus-arbitrum-2025-01-18",
                "status": "completed",
                "primary_tx_hash": "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                "tx_hashes": [
                    "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                    "0xf5e753d3da60db214f2261343c1e1bc46e674d2fa4b7a953eaf3c52123aeebd2",
                ],
                "transactions": [
                    {
                        "tx_hash": "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                        "status": "completed",
                    }
                ],
                "reasoning": {
                    "exploit_mechanism": "Technical analysis points to a price-manipulation path anchored by the exploit transaction.",
                },
                "validation": {
                    "verdict": "Technical validation passed.",
                    "unresolved_gaps": ["Funding path before the exploit still needs expansion."],
                },
                "merge_back": {
                    "summary": "Technical analysis anchored the exploit path with transaction-level evidence.",
                    "timeline_steps": [
                        {
                            "title": "Exploit transaction executes",
                            "detail": "The transaction-level path matches the public write-up.",
                            "tx_hashes": [
                                "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                            ],
                        }
                    ],
                    "fund_flow_path": [
                        {
                            "title": "Funds move out",
                            "detail": "The tx-level artifact shows funds leaving the victim path.",
                            "tx_hashes": [
                                "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                            ],
                        }
                    ],
                    "key_addresses": [
                        "0x56190CAC88b8D4b5D5Ed668ef81828913932e7Ed",
                    ],
                    "key_contracts": [
                        "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
                    ],
                    "key_transactions": [
                        "0x43aa42d2f11afe42832a9619bc8066dfb83a921798b91eaf9d0345dd27dcfb06",
                    ],
                    "open_questions": ["Funding path before the exploit still needs expansion."],
                },
            }
        )
    )


def test_analyst_report_endpoint_uses_fallback_builder(tmp_db: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "paribus-arbitrum-2025-01-18"
    _write_bundle(run_dir)

    from backend.app import app
    with patch("backend.database.settings") as db_s, \
         patch("backend.service.settings") as svc_s, \
         patch("backend.app.settings") as app_s:
        db_s.database_path = tmp_db
        svc_s.database_path = tmp_db
        svc_s.runs_dir = tmp_path
        app_s.api_token = ""
        app_s.cors_allow_origins = []
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/incidents/paribus-arbitrum-2025-01-18/analyst-report")

    assert response.status_code == 200
    body = response.json()
    # The unified builder populates headline from augmented_incident["title"],
    # which for this fixture is "Paribus" (not the old hardcoded Paribus-specific string).
    assert "Paribus" in body["case_overview"]["headline"]
    assert len(body["evidence_chain"]["claims"]) >= 1


def test_incident_bundle_normalizes_percent_style_completeness(tmp_db: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "paribus-arbitrum-2025-01-18"
    _write_bundle(run_dir)

    from backend.app import app
    with patch("backend.database.settings") as db_s, \
         patch("backend.service.settings") as svc_s, \
         patch("backend.app.settings") as app_s:
        db_s.database_path = tmp_db
        svc_s.database_path = tmp_db
        svc_s.runs_dir = tmp_path
        app_s.api_token = ""
        app_s.cors_allow_origins = []
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/incidents/paribus-arbitrum-2025-01-18")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_library_entry"]["completeness_score"] == 0.85
    assert body["quality_report"]["completeness_score"] == 0.85
    assert body["technical_analysis"]["status"] == "completed"

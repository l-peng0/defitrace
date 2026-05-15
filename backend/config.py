from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional import during bootstrap
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]

if load_dotenv:
    load_dotenv(ROOT / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else default


def _csv_from_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    runs_dir: Path = _path_from_env("CAPSTONE_RUNS_DIR", ROOT / "runs")
    database_path: Path = _path_from_env("CAPSTONE_DATABASE_PATH", ROOT / "backend" / "capstone.db")
    sample_targets_path: Path = _path_from_env(
        "CAPSTONE_SAMPLE_TARGETS_PATH",
        ROOT / "examples" / "sample_source_expansion_targets.json",
    )
    api_token: str = os.environ.get("CAPSTONE_API_TOKEN", "")
    glm_api_key: str = os.environ.get("GLM_API_KEY", "")
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    etherscan_api_key: str = os.environ.get("ETHERSCAN_API_KEY", "")
    bscscan_api_key: str = os.environ.get("BSCSCAN_API_KEY", "")
    rpc_eth: str = os.environ.get("CAPSTONE_RPC_ETH", "")
    rpc_bsc: str = os.environ.get("CAPSTONE_RPC_BSC", "")
    rpc_arb: str = os.environ.get("CAPSTONE_RPC_ARB", "")
    rpc_base: str = os.environ.get("CAPSTONE_RPC_BASE", "")
    rpc_opt: str = os.environ.get("CAPSTONE_RPC_OPT", "")
    rpc_polygon: str = os.environ.get("CAPSTONE_RPC_POLYGON", "")
    rpc_avax: str = os.environ.get("CAPSTONE_RPC_AVAX", "")
    cors_allow_origins: list[str] = field(
        default_factory=lambda: _csv_from_env("CAPSTONE_CORS_ALLOW_ORIGINS")
    )
    discovery_interval_seconds: int = int(
        os.environ.get("CAPSTONE_DISCOVERY_INTERVAL_SECONDS", "900")
    )
    session_ttl_seconds: int = int(
        os.environ.get("CAPSTONE_SESSION_TTL_SECONDS", str(60 * 60 * 24 * 30))
    )


settings = Settings()

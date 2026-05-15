# DeFiTrace

Multi-agent LLM pipeline for analyzing DeFi price-manipulation incidents.
Given a transaction hash and chain, it produces a structured security report
covering attacker profile, exploit path, fund flow, evidence chain, and an
analysis-completeness score.

## What it does

```
Incident seed (tx hash + chain)
        │
        ▼
  tx_deep_analysis          on-chain data collection
  (Etherscan / Alchemy /     receipt, callTracer, decoded calls,
   BSCScan + contract intel) funds flow, EIP-1967 proxy probing
        │
        ▼
  9-agent pipeline           Source Discovery → Technical
                             (Planner / Reasoner / Validator) →
                             Evidence Extraction → Pattern
                             Hypothesis → Timeline → Narrative →
                             Quality Assessor → QA Retry →
                             Report Assembler
        │
        ▼
  Structured run folder      JSON outputs ready for dashboard /
  data/fixtures/runs/<case>/ analyst report
```

## Repository layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI service, worker loop, SQLite operational state |
| `incident_augmentation/` | Augmentation pipeline + agents |
| `incident_collector/` | Source-document collection |
| `scripts/` | CLI entry points (run pipeline, build catalog, etc.) |
| `site/` | Vite + React dashboard frontend |
| `tests/unit/` | pytest unit suite |
| `data/fixtures/runs/` | Pre-computed pipeline outputs for 14 strict price-manipulation cases |
| `examples/` | Example incident seeds |

## Quick start

### Run the augmentation MVP on an example seed

```bash
pip install -r requirements.txt
python3 scripts/run_augmentation_mvp.py \
  --seed examples/incident_seed.example.json
```

Outputs are written under `runs/<incident_id>/`.

### Run the backend locally

```bash
python3 scripts/run_backend.py
```

Optional env vars:

- `CAPSTONE_API_TOKEN`, require `Authorization: Bearer <token>` on write endpoints
- `CAPSTONE_RUNS_DIR`, override where run folders are written
- `CAPSTONE_DATABASE_PATH`, override SQLite path
- `CAPSTONE_CORS_ALLOW_ORIGINS`, comma-separated allowed origins

### Run the frontend

```bash
cd site
npm install
npm run dev
```

## Dataset

14 curated price-manipulation incidents (Ethereum, BSC, Arbitrum, Base, 2024 to 2025).
Catalog: `data/incident_catalog_strict_pm14.csv`.
Each case has a complete pipeline run under `data/fixtures/runs/<case>/` for
inspection and reproducibility.

## Tests

```bash
pytest tests/unit -v
```

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Built as part of the HKUST MSc AI capstone project. Inspired by ideas in the
DeFiScope line of work on automatic price-manipulation detection.

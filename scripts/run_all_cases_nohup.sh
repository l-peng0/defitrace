#!/usr/bin/env bash
# Run all 14 strict-PM cases through the full 9-agent pipeline.
# Usage: bash scripts/run_all_cases_nohup.sh [--concurrency N]
#
# Output logs → logs/batch_run_<timestamp>.log
# Report JSON → data/fixtures/_batch_reports/batch-<timestamp>.json

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/batch_run_${TIMESTAMP}.log"
CONCURRENCY="${1:-2}"

mkdir -p "$LOG_DIR"

echo "=== DeFiScope Batch Run ===" | tee "$LOG_FILE"
echo "Started:     $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG_FILE"
echo "Concurrency: $CONCURRENCY" | tee -a "$LOG_FILE"
echo "Log:         $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

cd "$ROOT"

"$ROOT/.venv/bin/python" scripts/batch_run_sheet_cases.py \
    --run \
    --concurrency "$CONCURRENCY" \
    2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Finished: $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG_FILE"

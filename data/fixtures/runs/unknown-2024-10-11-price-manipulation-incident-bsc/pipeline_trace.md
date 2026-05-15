# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 383,579 ms (383.58 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 65.00 (threshold: 0.7). Missing/weak dimensions: protocol_name, loss_currency_denomination, exact_attack_timestamp, victim_contract_urls, attack_contract_urls, fund_flow_destination, root_cause_technical_detail. Quality assessor notes: The dossier provides a functional

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:57:05.661Z`
- **Duration**: 54,488 ms
- **Input**: 63 source docs; 495 heuristic items
- **Output**: 495 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:58:00.161Z`
- **Duration**: 1,306 ms
- **Input**: 1 tx(s): 0x9afcac8e82180fa5b2f346ca66cf6eb343cd1da5a2cd1b5117eb7eaaebe953b3
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:58:01.468Z`
- **Duration**: 10 ms
- **Input**: 1 transactions on BSC
- **Output**: 9 role categories; 18 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:58:01.478Z`
- **Duration**: 6,559 ms
- **Input**: 18 priority contracts
- **Output**: 18 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:58:08.037Z`
- **Duration**: 38,545 ms
- **Input**: 1 txs, 18 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:58:46.584Z`
- **Duration**: 4 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:58:46.594Z`
- **Duration**: 25,891 ms
- **Input**: 495 evidence items
- **Output**: executive_summary len=262
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:58:46.594Z`
- **Duration**: 25,891 ms
- **Input**: 495 evidence items
- **Output**: 4 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:59:12.492Z`
- **Duration**: 45,255 ms
- **Input**: 4 timeline steps; 4 narrative keys
- **Output**: completeness_score=65; judge_summary: The dossier provides a functional foundation with a clear attack timeline, verif
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:59:57.748Z`
- **Duration**: 68,612 ms
- **Input**: RETRY: 63 docs; critique injected
- **Output**: 495 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:01:06.362Z`
- **Duration**: 33,379 ms
- **Input**: RETRY: 495 evidence items
- **Output**: executive_summary len=234 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:01:06.362Z`
- **Duration**: 33,379 ms
- **Input**: RETRY: 495 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:01:39.743Z`
- **Duration**: 50,260 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=4
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

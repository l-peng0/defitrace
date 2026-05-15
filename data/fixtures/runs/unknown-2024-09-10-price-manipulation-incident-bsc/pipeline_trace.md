# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 310,139 ms (310.14 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 6.00 (threshold: 0.7). Missing/weak dimensions: exact_loss_amount_currency, cut_token_contract_address, flash_loan_details, precise_timestamps_block_numbers, technical_root_cause_analysis, attacker_funding_source, victim_contract_addresses, post_exploit_fund_destinatio

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:41:09.751Z`
- **Duration**: 3,120 ms
- **Input**: 62 source docs; 506 heuristic items
- **Output**: 506 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:41:12.876Z`
- **Duration**: 1,200 ms
- **Input**: 1 tx(s): 0x2c123d08ca3d50c4b875c0b5de1b5c85d0bf9979dffbf87c48526e3a67396827
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:41:14.076Z`
- **Duration**: 14 ms
- **Input**: 1 transactions on BSC
- **Output**: 9 role categories; 13 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:41:14.090Z`
- **Duration**: 1,596 ms
- **Input**: 13 priority contracts
- **Output**: 12 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:41:15.686Z`
- **Duration**: 65,299 ms
- **Input**: 1 txs, 12 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:42:20.983Z`
- **Duration**: 4 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:42:20.990Z`
- **Duration**: 35,813 ms
- **Input**: 506 evidence items
- **Output**: executive_summary len=326
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:42:20.990Z`
- **Duration**: 35,813 ms
- **Input**: 506 evidence items
- **Output**: 5 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:42:56.810Z`
- **Duration**: 47,406 ms
- **Input**: 5 timeline steps; 4 narrative keys
- **Output**: completeness_score=6.0; judge_summary: This dossier captures the skeletal structure of a price manipulation attack targ
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:43:44.215Z`
- **Duration**: 3,400 ms
- **Input**: RETRY: 62 docs; critique injected
- **Output**: 506 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:43:47.615Z`
- **Duration**: 37,705 ms
- **Input**: RETRY: 506 evidence items
- **Output**: executive_summary len=270 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:43:47.615Z`
- **Duration**: 37,705 ms
- **Input**: RETRY: 506 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:44:25.320Z`
- **Duration**: 41,064 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=0.42
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

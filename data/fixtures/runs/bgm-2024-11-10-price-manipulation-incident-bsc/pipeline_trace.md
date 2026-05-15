# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 430,259 ms (430.26 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 72.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, poc_links, block_number, timestamp, fund_flow_analysis, attacker_funding_source, detailed_transaction_trace. Quality assessor notes: The BGM price manipulation incident dossier

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:07:33.573Z`
- **Duration**: 26,779 ms
- **Input**: 60 source docs; 476 heuristic items
- **Output**: 476 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:08:00.364Z`
- **Duration**: 1,158 ms
- **Input**: 1 tx(s): 0x8580825008800b9e13266f40b41a838a521e4d0bb4abc1cb78684253b7bc9fd1
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:08:01.522Z`
- **Duration**: 3 ms
- **Input**: 1 transactions on BSC
- **Output**: 9 role categories; 4 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:08:01.526Z`
- **Duration**: 2,341 ms
- **Input**: 4 priority contracts
- **Output**: 3 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:08:03.867Z`
- **Duration**: 30,023 ms
- **Input**: 1 txs, 3 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:08:33.891Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:08:33.895Z`
- **Duration**: 26,584 ms
- **Input**: 476 evidence items
- **Output**: executive_summary len=442
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:08:33.895Z`
- **Duration**: 26,584 ms
- **Input**: 476 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:09:00.487Z`
- **Duration**: 31,459 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=72; judge_summary: The BGM price manipulation incident dossier captures core elements including the
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:09:31.946Z`
- **Duration**: 67,814 ms
- **Input**: RETRY: 60 docs; critique injected
- **Output**: 494 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:10:39.762Z`
- **Duration**: 87,258 ms
- **Input**: RETRY: 494 evidence items
- **Output**: executive_summary len=298 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:10:39.762Z`
- **Duration**: 87,258 ms
- **Input**: RETRY: 494 evidence items
- **Output**: 5 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:12:07.023Z`
- **Duration**: 42,997 ms
- **Input**: RETRY: 5 steps; 4 narrative keys
- **Output**: v2 completeness_score=62
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 378,828 ms (378.83 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 5.50 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, social_sources, exact_timestamp, block_number, specific_asset_targeted, manipulation_mechanism_details, fund_destination_addresses, protocol_response_statement. Quality assessor

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:46:57.863Z`
- **Duration**: 25,635 ms
- **Input**: 45 source docs; 334 heuristic items
- **Output**: 334 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:47:23.506Z`
- **Duration**: 1,118 ms
- **Input**: 1 tx(s): 0xb5cfa4ae4d6e459ba285fec7f31caf8885e2285a0b4ff62f66b43e280c947216
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:47:24.625Z`
- **Duration**: 8 ms
- **Input**: 1 transactions on Arbitrum
- **Output**: 9 role categories; 12 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:47:24.632Z`
- **Duration**: 8,346 ms
- **Input**: 12 priority contracts
- **Output**: 12 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:47:32.978Z`
- **Duration**: 84,943 ms
- **Input**: 1 txs, 12 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:48:57.920Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:48:57.925Z`
- **Duration**: 33,057 ms
- **Input**: 334 evidence items
- **Output**: executive_summary len=397
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:48:57.925Z`
- **Duration**: 33,057 ms
- **Input**: 334 evidence items
- **Output**: 4 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:49:30.988Z`
- **Duration**: 32,873 ms
- **Input**: 4 timeline steps; 4 narrative keys
- **Output**: completeness_score=5.5; judge_summary: The LavaLending incident dossier provides the essential skeleton of a price mani
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:50:03.860Z`
- **Duration**: 46,996 ms
- **Input**: RETRY: 45 docs; critique injected
- **Output**: 341 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:50:50.855Z`
- **Duration**: 34,904 ms
- **Input**: RETRY: 341 evidence items
- **Output**: executive_summary len=312 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:50:50.855Z`
- **Duration**: 34,904 ms
- **Input**: RETRY: 341 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:51:25.759Z`
- **Duration**: 42,986 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=5.2
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 260,382 ms (260.38 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 0.58 (threshold: 0.7). Missing/weak dimensions: protocol_name_actual, attack_contract_urls, victim_contract_urls, social_sources, block_number, fund_tracing, oracle_contract_address, precise_loss_breakdown. Quality assessor notes: The dossier captures essential on-chai

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:02:42.923Z`
- **Duration**: 3,280 ms
- **Input**: 46 source docs; 401 heuristic items
- **Output**: 401 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:02:46.210Z`
- **Duration**: 1,724 ms
- **Input**: 1 tx(s): 0x6ab5b7b51f780e8c6c5ddaf65e9badb868811a95c1fd64e86435283074d3149e
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:02:47.934Z`
- **Duration**: 14 ms
- **Input**: 1 transactions on Base
- **Output**: 9 role categories; 3 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:02:47.948Z`
- **Duration**: 4,515 ms
- **Input**: 3 priority contracts
- **Output**: 3 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:02:52.463Z`
- **Duration**: 57,202 ms
- **Input**: 1 txs, 3 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:03:49.667Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:03:49.673Z`
- **Duration**: 23,321 ms
- **Input**: 401 evidence items
- **Output**: executive_summary len=291
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:03:49.673Z`
- **Duration**: 23,321 ms
- **Input**: 401 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:04:13.001Z`
- **Duration**: 64,821 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=0.58; judge_summary: The dossier captures essential on-chain evidence for a price manipulation attack
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:05:17.823Z`
- **Duration**: 3,852 ms
- **Input**: RETRY: 46 docs; critique injected
- **Output**: 401 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:05:21.676Z`
- **Duration**: 16,028 ms
- **Input**: RETRY: 401 evidence items
- **Output**: executive_summary len=333 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:05:21.676Z`
- **Duration**: 16,028 ms
- **Input**: RETRY: 401 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:05:37.704Z`
- **Duration**: 46,275 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=58
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

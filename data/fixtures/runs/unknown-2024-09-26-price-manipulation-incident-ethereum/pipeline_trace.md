# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 431,833 ms (431.83 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 48.00 (threshold: 0.7). Missing/weak dimensions: precise_loss_amount_with_currency, attack_contract_addresses, victim_contract_addresses, block_number, exact_timestamp, fund_flow_tracing, social_media_sources, protocol_official_response, recovery_status. Quality assess

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:40:24.755Z`
- **Duration**: 92,326 ms
- **Input**: 45 source docs; 340 heuristic items
- **Output**: 340 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:41:57.086Z`
- **Duration**: 1,256 ms
- **Input**: 1 tx(s): 0x725f0d65340c859e0f64e72ca8260220c526c3e0ccde530004160809f6177940
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:41:58.341Z`
- **Duration**: 2 ms
- **Input**: 1 transactions on Ethereum
- **Output**: 9 role categories; 4 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:41:58.343Z`
- **Duration**: 1,645 ms
- **Input**: 4 priority contracts
- **Output**: 4 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:41:59.988Z`
- **Duration**: 42,223 ms
- **Input**: 1 txs, 4 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:42:42.210Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:42:42.214Z`
- **Duration**: 24,866 ms
- **Input**: 340 evidence items
- **Output**: executive_summary len=376
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:42:42.214Z`
- **Duration**: 24,866 ms
- **Input**: 340 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:43:07.086Z`
- **Duration**: 31,041 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=48; judge_summary: The dossier contains essential attack artifacts including a confirmed transactio
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:43:38.126Z`
- **Duration**: 119,068 ms
- **Input**: RETRY: 45 docs; critique injected
- **Output**: 359 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:45:37.192Z`
- **Duration**: 35,399 ms
- **Input**: RETRY: 359 evidence items
- **Output**: executive_summary len=455 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:45:37.192Z`
- **Duration**: 35,399 ms
- **Input**: RETRY: 359 evidence items
- **Output**: 4 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:46:12.590Z`
- **Duration**: 23,741 ms
- **Input**: RETRY: 4 steps; 4 narrative keys
- **Output**: v2 completeness_score=42
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

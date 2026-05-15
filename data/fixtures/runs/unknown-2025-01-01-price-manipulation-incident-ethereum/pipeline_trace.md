# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 410,948 ms (410.95 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 68.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, social_sources, precise_loss_amount_with_units, exact_timestamp_or_block_number, fund_flow_tracing, attacker_profiling, protocol_response. Quality assessor notes: This dossier 

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:12:59.160Z`
- **Duration**: 3,024 ms
- **Input**: 45 source docs; 334 heuristic items
- **Output**: 334 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:13:02.192Z`
- **Duration**: 1,070 ms
- **Input**: 1 tx(s): 0xef34f4fdf03e403e3c94e96539354fb4fe0b79a5ec927eacc63bc04108dbf420
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:13:03.261Z`
- **Duration**: 2 ms
- **Input**: 1 transactions on Ethereum
- **Output**: 9 role categories; 4 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:13:03.263Z`
- **Duration**: 2,030 ms
- **Input**: 4 priority contracts
- **Output**: 3 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:13:05.293Z`
- **Duration**: 33,748 ms
- **Input**: 1 txs, 3 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:13:39.042Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:13:39.047Z`
- **Duration**: 38,791 ms
- **Input**: 334 evidence items
- **Output**: executive_summary len=338
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:13:39.047Z`
- **Duration**: 38,791 ms
- **Input**: 334 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:14:17.842Z`
- **Duration**: 42,369 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=68; judge_summary: This dossier provides a functional foundation for the LAURA Token price manipula
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:15:00.213Z`
- **Duration**: 110,768 ms
- **Input**: RETRY: 45 docs; critique injected
- **Output**: 334 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:16:50.984Z`
- **Duration**: 52,887 ms
- **Input**: RETRY: 334 evidence items
- **Output**: executive_summary len=0 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:16:50.984Z`
- **Duration**: 52,887 ms
- **Input**: RETRY: 334 evidence items
- **Output**: 5 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:17:43.872Z`
- **Duration**: 34,580 ms
- **Input**: RETRY: 5 steps; 0 narrative keys
- **Output**: v2 completeness_score=58
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

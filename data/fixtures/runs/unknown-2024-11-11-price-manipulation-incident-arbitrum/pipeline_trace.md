# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 286,646 ms (286.65 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 45.00 (threshold: 0.7). Missing/weak dimensions: confirmed_protocol_name, actual_loss_amount, attack_contract_addresses, victim_contract_addresses, root_cause_detail, fund_flow_tracing, social_media_sources, official_protocol_statement, recovery_status. Quality assesso

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:08:26.381Z`
- **Duration**: 32,420 ms
- **Input**: 46 source docs; 362 heuristic items
- **Output**: 362 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:08:58.829Z`
- **Duration**: 1,955 ms
- **Input**: 1 tx(s): 0x6a2f989b5493b52ffc078d0a59a3bf9727d134b403aa6e0bf309fd513a728f7f
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:09:00.784Z`
- **Duration**: 5 ms
- **Input**: 1 transactions on Arbitrum
- **Output**: 9 role categories; 1 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:09:00.789Z`
- **Duration**: 3,657 ms
- **Input**: 1 priority contracts
- **Output**: 1 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:09:04.447Z`
- **Duration**: 44,438 ms
- **Input**: 1 txs, 1 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:09:48.886Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:09:48.891Z`
- **Duration**: 34,958 ms
- **Input**: 362 evidence items
- **Output**: executive_summary len=395
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:09:48.891Z`
- **Duration**: 34,958 ms
- **Input**: 362 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:10:23.853Z`
- **Duration**: 31,783 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=45; judge_summary: This dossier has foundational elements including a verified transaction hash, at
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:10:55.638Z`
- **Duration**: 4,132 ms
- **Input**: RETRY: 46 docs; critique injected
- **Output**: 362 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:10:59.770Z`
- **Duration**: 24,186 ms
- **Input**: RETRY: 362 evidence items
- **Output**: executive_summary len=449 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:10:59.770Z`
- **Duration**: 24,186 ms
- **Input**: RETRY: 362 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:11:23.957Z`
- **Duration**: 49,967 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=55
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

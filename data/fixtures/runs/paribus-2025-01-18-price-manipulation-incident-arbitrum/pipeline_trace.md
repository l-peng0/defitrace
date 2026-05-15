# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 472,151 ms (472.15 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 68.00 (threshold: 0.7). Missing/weak dimensions: incident_date, oracle_mechanism_details, victim_contract_urls, attack_contract_urls, fund_flow_post_attack, protocol_response, ev-033 reference is broken. Quality assessor notes: The dossier captures the essential elemen

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:18:18.508Z`
- **Duration**: 44,295 ms
- **Input**: 50 source docs; 365 heuristic items
- **Output**: 365 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:19:02.810Z`
- **Duration**: 2,686 ms
- **Input**: 1 tx(s): 0xf5e753d3da60db214f2261343c1e1bc46e674d2fa4b7a953eaf3c52123aeebd2
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:19:05.496Z`
- **Duration**: 24 ms
- **Input**: 1 transactions on Arbitrum
- **Output**: 9 role categories; 6 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:19:05.520Z`
- **Duration**: 13,291 ms
- **Input**: 6 priority contracts
- **Output**: 6 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:19:18.812Z`
- **Duration**: 53,346 ms
- **Input**: 1 txs, 6 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:20:12.160Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:20:12.168Z`
- **Duration**: 58,968 ms
- **Input**: 365 evidence items
- **Output**: executive_summary len=290
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:20:12.168Z`
- **Duration**: 58,968 ms
- **Input**: 365 evidence items
- **Output**: 5 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:21:11.145Z`
- **Duration**: 35,889 ms
- **Input**: 5 timeline steps; 4 narrative keys
- **Output**: completeness_score=68; judge_summary: The dossier captures the essential elements of a price-manipulation attack again
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:21:47.036Z`
- **Duration**: 70,297 ms
- **Input**: RETRY: 50 docs; critique injected
- **Output**: 389 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:22:57.335Z`
- **Duration**: 55,687 ms
- **Input**: RETRY: 389 evidence items
- **Output**: executive_summary len=448 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:22:57.335Z`
- **Duration**: 55,687 ms
- **Input**: RETRY: 389 evidence items
- **Output**: 6 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:23:53.024Z`
- **Duration**: 23,012 ms
- **Input**: RETRY: 6 steps; 4 narrative keys
- **Output**: v2 completeness_score=0.78
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

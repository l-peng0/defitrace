# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 714,272 ms (714.27 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 4.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, precise_incident_timestamp, confirmed_protocol_name, detailed_loss_breakdown, vulnerability_root_cause_technical_details, fund_flow_post_attack, attack_preparation_steps. Qualit

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:57:07.924Z`
- **Duration**: 3,194 ms
- **Input**: 63 source docs; 497 heuristic items
- **Output**: 497 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:57:11.132Z`
- **Duration**: 1,080 ms
- **Input**: 1 tx(s): 0xa9df1bd97cf6d4d1d58d3adfbdde719e46a1548db724c2e76b4cd4c3222f22b3
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:57:12.212Z`
- **Duration**: 3 ms
- **Input**: 1 transactions on BSC
- **Output**: 9 role categories; 6 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:57:12.215Z`
- **Duration**: 13,161 ms
- **Input**: 6 priority contracts
- **Output**: 6 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:57:25.376Z`
- **Duration**: 188,736 ms
- **Input**: 1 txs, 6 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:00:34.117Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:00:34.124Z`
- **Duration**: 38,531 ms
- **Input**: 497 evidence items
- **Output**: executive_summary len=370
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:00:34.124Z`
- **Duration**: 38,531 ms
- **Input**: 497 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:01:12.659Z`
- **Duration**: 47,180 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=4; judge_summary: The dossier establishes a basic incident skeleton with verified attack transacti
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:01:59.840Z`
- **Duration**: 229,914 ms
- **Input**: RETRY: 63 docs; critique injected
- **Output**: 518 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:05:49.762Z`
- **Duration**: 52,283 ms
- **Input**: RETRY: 518 evidence items
- **Output**: executive_summary len=417 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:05:49.762Z`
- **Duration**: 52,283 ms
- **Input**: RETRY: 518 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:06:42.047Z`
- **Duration**: 49,375 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=52
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

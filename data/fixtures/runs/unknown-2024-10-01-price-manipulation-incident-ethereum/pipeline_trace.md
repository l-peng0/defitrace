# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 316,459 ms (316.46 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 2.50 (threshold: 0.7). Missing/weak dimensions: protocol_name, loss_amount_with_unit, attack_mechanics_detail, root_cause_analysis, fund_flow_tracing, narrative_section, attack_contract_urls, victim_contract_urls, social_sources, incident_date_confirmation, vulnerabili

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:45:21.383Z`
- **Duration**: 3,089 ms
- **Input**: 44 source docs; 313 heuristic items
- **Output**: 313 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:45:24.476Z`
- **Duration**: 1,057 ms
- **Input**: 1 tx(s): 0xd20b3b31a682322eb0698ecd67a6d8a040ccea653ba429ec73e3584fa176ff2b
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:45:25.533Z`
- **Duration**: 7 ms
- **Input**: 1 transactions on Ethereum
- **Output**: 9 role categories; 17 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:45:25.540Z`
- **Duration**: 870 ms
- **Input**: 17 priority contracts
- **Output**: 16 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:45:26.411Z`
- **Duration**: 66,622 ms
- **Input**: 1 txs, 16 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:46:33.031Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:46:33.036Z`
- **Duration**: 26,245 ms
- **Input**: 313 evidence items
- **Output**: executive_summary len=0
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:46:33.036Z`
- **Duration**: 26,245 ms
- **Input**: 313 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:46:59.285Z`
- **Duration**: 48,962 ms
- **Input**: 3 timeline steps; 0 narrative keys
- **Output**: completeness_score=2.5; judge_summary: This dossier is critically incomplete and unsuitable for presentation. The proto
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:47:48.246Z`
- **Duration**: 36,367 ms
- **Input**: RETRY: 44 docs; critique injected
- **Output**: 319 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:48:24.612Z`
- **Duration**: 29,869 ms
- **Input**: RETRY: 319 evidence items
- **Output**: executive_summary len=486 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:48:24.612Z`
- **Duration**: 29,869 ms
- **Input**: RETRY: 319 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:48:54.480Z`
- **Duration**: 47,256 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=28
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 364,292 ms (364.29 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 78.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, fund_flow_tracing, detailed_technical_root_cause, vulnerable_contract_identification. Quality assessor notes: The Veth incident dossier provides adequate foundational coverage 

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:12:41.634Z`
- **Duration**: 76,721 ms
- **Input**: 139 source docs; 612 heuristic items
- **Output**: 612 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T13:13:58.371Z`
- **Duration**: 907 ms
- **Input**: 1 tx(s): 0x900891b4540cac8443d6802a08a7a0562b5320444aa6d8eed19705ea6fb9710b
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T13:13:59.278Z`
- **Duration**: 2 ms
- **Input**: 1 transactions on Ethereum
- **Output**: 9 role categories; 2 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T13:13:59.279Z`
- **Duration**: 1,984 ms
- **Input**: 2 priority contracts
- **Output**: 1 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T13:14:01.263Z`
- **Duration**: 77,638 ms
- **Input**: 1 txs, 1 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T13:15:18.904Z`
- **Duration**: 1 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:15:18.908Z`
- **Duration**: 37,052 ms
- **Input**: 612 evidence items
- **Output**: executive_summary len=299
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:15:18.908Z`
- **Duration**: 37,052 ms
- **Input**: 612 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:15:55.964Z`
- **Duration**: 49,550 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=78; judge_summary: The Veth incident dossier provides adequate foundational coverage with verified 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T13:16:45.516Z`
- **Duration**: 3,604 ms
- **Input**: RETRY: 139 docs; critique injected
- **Output**: 612 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T13:16:49.120Z`
- **Duration**: 14,714 ms
- **Input**: RETRY: 612 evidence items
- **Output**: executive_summary len=279 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T13:16:49.120Z`
- **Duration**: 14,714 ms
- **Input**: RETRY: 612 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T13:17:03.835Z`
- **Duration**: 50,353 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=72
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

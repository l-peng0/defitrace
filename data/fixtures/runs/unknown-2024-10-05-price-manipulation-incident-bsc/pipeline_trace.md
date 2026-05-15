# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 397,467 ms (397.47 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 58.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, social_sources, protocol_name_confirmed, loss_amount_unit, fund_flow_tracing, root_cause_detail. Quality assessor notes: The dossier captures a price manipulation attack on BSC

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:50:38.054Z`
- **Duration**: 3,509 ms
- **Input**: 61 source docs; 482 heuristic items
- **Output**: 482 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:50:41.573Z`
- **Duration**: 1,194 ms
- **Input**: 1 tx(s): 0x5e694707337cca979d18f9e45f40e81d6ca341ed342f1377f563e779a746460d
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:50:42.768Z`
- **Duration**: 7 ms
- **Input**: 1 transactions on BSC
- **Output**: 9 role categories; 2 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:50:42.774Z`
- **Duration**: 4,521 ms
- **Input**: 2 priority contracts
- **Output**: 2 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:50:47.295Z`
- **Duration**: 55,986 ms
- **Input**: 1 txs, 2 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:51:43.280Z`
- **Duration**: 3 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:51:43.286Z`
- **Duration**: 44,632 ms
- **Input**: 482 evidence items
- **Output**: executive_summary len=282
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:51:43.286Z`
- **Duration**: 44,632 ms
- **Input**: 482 evidence items
- **Output**: 4 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:52:27.919Z`
- **Duration**: 39,929 ms
- **Input**: 4 timeline steps; 4 narrative keys
- **Output**: completeness_score=58; judge_summary: The dossier captures a price manipulation attack on BSC with core on-chain artif
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:53:07.848Z`
- **Duration**: 109,668 ms
- **Input**: RETRY: 61 docs; critique injected
- **Output**: 505 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:54:57.688Z`
- **Duration**: 25,384 ms
- **Input**: RETRY: 505 evidence items
- **Output**: executive_summary len=240 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:54:57.688Z`
- **Duration**: 25,384 ms
- **Input**: RETRY: 505 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:55:23.073Z`
- **Duration**: 42,618 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=62
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

# Pipeline Trace

## Run Summary

- **Agents recorded**: 13
- **Total wall time**: 275,000 ms (275.00 s)
- **Revision loop**: ✗ not triggered
- **QA retry loop**: ✓ triggered

> **QA retry critique** (Quality Assessor → Evidence Extractor):
> First-pass completeness score: 58.00 (threshold: 0.7). Missing/weak dimensions: attack_contract_urls, victim_contract_urls, social_sources, sasha_token_contract_address, lp_pair_address, flash_loan_provider, fund_destination_tracing, block_number, detailed_attack_flow_steps. Quality assessor notes: 

## Agent Timeline

### 1. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:52:17.967Z`
- **Duration**: 5,532 ms
- **Input**: 45 source docs; 346 heuristic items
- **Output**: 346 total items (+0 LLM-extracted)
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 2. `collector` [rule]

- **Started**: `2026-04-27T12:52:23.507Z`
- **Duration**: 1,009 ms
- **Input**: 1 tx(s): 0xd9fdc7d03eec28fc2453c5fa68eff82d4c297f436a6a5470c54ca3aecd2db17e
- **Output**: 1 artifact bundle(s) collected; statuses: completed

### 3. `planner` [rule]

- **Started**: `2026-04-27T12:52:24.516Z`
- **Duration**: 2 ms
- **Input**: 1 transactions on Ethereum
- **Output**: 9 role categories; 4 priority contracts

### 4. `contract_intelligence` [rule]

- **Started**: `2026-04-27T12:52:24.517Z`
- **Duration**: 6,330 ms
- **Input**: 4 priority contracts
- **Output**: 3 contracts in inventory

### 5. `technical_reasoner` [LLM]

- **Started**: `2026-04-27T12:52:30.848Z`
- **Duration**: 46,304 ms
- **Input**: 1 txs, 3 contracts
- **Output**: 0 timeline steps; mechanism: 
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 6. `semantic_validator` [rule]

- **Started**: `2026-04-27T12:53:17.150Z`
- **Duration**: 0 ms
- **Input**: revision_round=0
- **Output**: severity=pass; needs_revision=False; verdict: Deterministic and semantic checks passed.

### 7. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:53:17.153Z`
- **Duration**: 24,044 ms
- **Input**: 346 evidence items
- **Output**: executive_summary len=365
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 8. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:53:17.153Z`
- **Duration**: 24,044 ms
- **Input**: 346 evidence items
- **Output**: 3 timeline steps
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 9. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:53:41.202Z`
- **Duration**: 50,862 ms
- **Input**: 3 timeline steps; 4 narrative keys
- **Output**: completeness_score=58; judge_summary: The dossier establishes core incident facts with solid evidence: a confirmed att
- **LLM provider**: unknown
- **Notes**: tokens: not captured (response parsed internally)

### 10. `evidence_extractor` [LLM]

- **Started**: `2026-04-27T12:54:32.237Z`
- **Duration**: 3,246 ms
- **Input**: RETRY: 45 docs; critique injected
- **Output**: 346 items after retry extraction
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 11. `narrative_writer` [LLM]

- **Started**: `2026-04-27T12:54:35.482Z`
- **Duration**: 34,919 ms
- **Input**: RETRY: 346 evidence items
- **Output**: executive_summary len=330 (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 12. `timeline_synthesizer` [LLM]

- **Started**: `2026-04-27T12:54:35.482Z`
- **Duration**: 34,919 ms
- **Input**: RETRY: 346 evidence items
- **Output**: 3 timeline steps (v2)
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

### 13. `quality_assessor` [LLM]

- **Started**: `2026-04-27T12:55:10.403Z`
- **Duration**: 43,789 ms
- **Input**: RETRY: 3 steps; 4 narrative keys
- **Output**: v2 completeness_score=62
- **LLM provider**: unknown
- **Notes**: QA retry pass; tokens: not captured (response parsed internally)

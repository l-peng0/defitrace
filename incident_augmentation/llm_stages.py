"""LLM-powered augmentation agents."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .model_runtime import call_llm

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


_SECTION_HEADER_RE = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


def _extract_prompt_section(template: str, header: str) -> str:
    """Return the body of the `## <header>` section, trimmed.

    A section spans from immediately after its header line up to the next `## `
    header or end of file. Raises IndexError (matching the legacy
    `.split(...)[1]` behaviour) when the header is absent.
    """
    matches = list(_SECTION_HEADER_RE.finditer(template))
    for i, match in enumerate(matches):
        if match.group(1).strip() == header:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(template)
            return template[start:end].strip("\n").strip()
    # Mirror the original ".split(...)[1]" IndexError on missing section.
    raise IndexError(f"prompt section '## {header}' not found")


def _extract_json(text: str) -> str:
    """Strip markdown code fences that some LLMs add despite 'Return ONLY JSON'."""
    text = text.strip()
    if text.startswith("```"):
        # drop the opening fence line (```json or ```)
        text = text.split("\n", 1)[-1]
        # drop the closing fence
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _build_incident_context(seed_dict: dict[str, Any]) -> str:
    parts = [
        f"Protocol: {seed_dict.get('protocol_name') or seed_dict.get('incident_name') or 'unknown'}",
        f"Chain: {seed_dict.get('chain', 'unknown')}",
        f"Date: {seed_dict.get('incident_date', 'unknown')}",
    ]
    if seed_dict.get("summary_candidates"):
        parts.append(f"Summary hint: {seed_dict['summary_candidates'][0][:300]}")
    return "\n".join(parts)


def run_llm_evidence_extractor(
    seed_dict: dict[str, Any],
    source_documents: dict[str, Any],
    existing_raw_evidence: dict[str, Any],
    incident_id: str,
    retry_critique: str | None = None,
) -> dict[str, Any]:
    """Agent 1: Extract structured evidence from source text. Falls back to heuristic on failure.

    Args:
        retry_critique: When provided (QA retry pass), injected at the top of the user prompt
            so the LLM can focus extraction on the dimensions flagged as missing/weak by the
            Quality Assessor.  None on the first pass.
    """
    try:
        template = _load_prompt("evidence_extractor")
        excerpts = "\n\n".join(
            f"[{doc.get('url', '')}]\n{doc.get('text_excerpt', '')[:3000]}"
            for doc in source_documents.get("documents", [])
            if doc.get("text_excerpt")
        )
        if not excerpts:
            return existing_raw_evidence

        system_prompt = _extract_prompt_section(template, "System")
        base_user_prompt = (
            _extract_prompt_section(template, "Input")
            .replace("{incident_context}", _build_incident_context(seed_dict))
            .replace("{source_excerpts}", excerpts)
        )
        # Inject QA critique at the very top of the user prompt so it acts as a focal lens.
        # Timeline/Narrative stages are NOT given the critique directly; they consume the
        # re-extracted evidence produced here, which already incorporates the QA feedback.
        if retry_critique:
            critique_header = (
                "REVISION REQUEST FROM QUALITY ASSESSOR:\n"
                f"{retry_critique}\n\n"
                "Please pay special attention to extracting evidence that addresses the "
                "above gaps. Then proceed with normal extraction below.\n\n"
            )
            user_prompt = critique_header + base_user_prompt
        else:
            user_prompt = base_user_prompt
        raw = call_llm(system_prompt, user_prompt, incident_id, "llm_evidence_extractor")
        llm_items: list[dict] = json.loads(_extract_json(raw))

        normalized: list[dict] = []
        for i, item in enumerate(llm_items):
            if not isinstance(item, dict):
                continue
            item.setdefault("fact_type", item.get("type", "unknown"))
            item.setdefault("fact_value", item.get("value", ""))
            item.setdefault("fact_text", item.get("fact_text") or item.get("value", ""))
            item.setdefault("evidence_id", f"llm-ev-{i + 1:03d}")
            item.setdefault("source_ref", "")
            item.setdefault("source_url", item.get("source_url", ""))
            item.setdefault("source_type", "llm_extracted")
            item.setdefault("is_inferred", False)
            item.setdefault("confidence", float(item.get("confidence", 0.8)))
            # Skip items still missing required fields
            if not item.get("fact_type") or not item.get("fact_text"):
                continue
            normalized.append(item)

        merged = list(existing_raw_evidence.get("evidence_items", [])) + normalized
        return {**existing_raw_evidence, "evidence_items": merged}

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "llm.fallback",
            extra={"stage": "llm_evidence_extractor", "incident_id": incident_id, "error": str(exc)},
        )
        return existing_raw_evidence


def run_llm_timeline_synthesizer(
    seed_dict: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    heuristic_timeline: dict[str, Any],
    incident_id: str,
) -> dict[str, Any]:
    """Agent 2: Synthesize causal attack timeline. Falls back to heuristic on failure."""
    try:
        template = _load_prompt("timeline_synthesizer")
        system_prompt = _extract_prompt_section(template, "System")
        user_prompt = (
            _extract_prompt_section(template, "Input")
            .replace("{incident_context}", _build_incident_context(seed_dict))
            .replace("{evidence_items}", json.dumps(evidence_items[:40], ensure_ascii=True))
        )
        raw = call_llm(system_prompt, user_prompt, incident_id, "llm_timeline_synthesizer")
        timeline = json.loads(_extract_json(raw))
        if "steps" not in timeline:
            raise ValueError(f"LLM response missing required key 'steps': {list(timeline.keys())}")
        timeline.setdefault("incident_id", incident_id)
        return timeline

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "llm.fallback",
            extra={"stage": "llm_timeline_synthesizer", "incident_id": incident_id, "error": str(exc)},
        )
        return heuristic_timeline


def run_llm_narrative_writer(
    seed_dict: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    incident_id: str,
) -> dict[str, Any]:
    """Agent 3: Write executive summary and attack narrative. Returns {} on failure."""
    try:
        template = _load_prompt("narrative_writer")
        system_prompt = _extract_prompt_section(template, "System")
        user_prompt = (
            _extract_prompt_section(template, "Input")
            .replace("{incident_context}", _build_incident_context(seed_dict))
            .replace("{evidence_items}", json.dumps(evidence_items[:40], ensure_ascii=True))
        )
        raw = call_llm(system_prompt, user_prompt, incident_id, "llm_narrative_writer")
        result = json.loads(_extract_json(raw))
        required = {"executive_summary", "attack_narrative", "attacker_motive", "key_takeaway"}
        missing = required - result.keys()
        if missing:
            raise ValueError(f"LLM narrative missing required keys: {missing}")
        return result

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "llm.fallback",
            extra={"stage": "llm_narrative_writer", "incident_id": incident_id, "error": str(exc)},
        )
        return {}


def run_llm_quality_assessor(
    seed_dict: dict[str, Any],
    dossier_draft: dict[str, Any],
    incident_id: str,
) -> dict[str, Any]:
    """Agent 4: Assess dossier completeness. Falls back to heuristic_quality_report on failure."""
    try:
        template = _load_prompt("quality_assessor")
        system_prompt = _extract_prompt_section(template, "System")
        user_prompt = (
            _extract_prompt_section(template, "Input")
            .replace("{incident_context}", _build_incident_context(seed_dict))
            .replace("{timeline}", json.dumps(dossier_draft.get("timeline", {}), ensure_ascii=True))
            .replace("{narrative}", json.dumps(dossier_draft.get("narrative", {}), ensure_ascii=True))
            .replace("{evidence_items}", json.dumps(dossier_draft.get("evidence_items", [])[:30], ensure_ascii=True))
            .replace("{source_count}", str(dossier_draft.get("source_count", 0)))
            .replace("{heuristic_missing_fields}", json.dumps(dossier_draft.get("heuristic_missing_fields", [])))
        )
        raw = call_llm(system_prompt, user_prompt, incident_id, "llm_quality_assessor")
        result = json.loads(_extract_json(raw))
        required = {"completeness_score", "judge_summary"}
        missing = required - result.keys()
        if missing:
            raise ValueError(f"LLM quality report missing required keys: {missing}")
        result.setdefault("missing_fields", [])
        return result

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "llm.fallback",
            extra={"stage": "llm_quality_assessor", "incident_id": incident_id, "error": str(exc)},
        )
        return dossier_draft.get("heuristic_quality_report", {
            "completeness_score": 0.5,
            "judge_summary": "Quality assessment unavailable (LLM fallback).",
            "missing_fields": [],
        })

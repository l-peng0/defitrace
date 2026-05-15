"""Transparent observability layer for the 9-agent DeFi analysis pipeline.

Each agent invocation is wrapped in a ``TraceCollector.record()`` context manager
that captures start time, wall-clock duration, and optional LLM token usage.

Token usage strategy
--------------------
The LLM stages in ``llm_stages.py`` call ``call_llm()`` from ``model_runtime.py``
and return only the parsed result dict — the raw SDK response (which carries
``usage.prompt_tokens`` / ``usage.completion_tokens``) is consumed internally.
Propagating token counts without changing the stage function signatures would be
invasive and would risk breaking the existing 77 tests.

Decision: store ``prompt_tokens=None`` and ``completion_tokens=None`` for LLM
agents and add ``notes="tokens: not captured (response parsed internally)"``.
Callers that *do* have token info (e.g. future refactors or direct SDK use) can
set them on the mutable ``slot`` object inside the ``with trace.record(...)``
block before the block exits.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class AgentTraceRecord:
    """One row in the pipeline trace — one agent invocation."""

    agent_name: str
    agent_type: str  # "rule" | "llm"
    started_at: str  # UTC ISO 8601
    duration_ms: int
    input_summary: str = ""
    output_summary: str = ""
    llm_provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "llm_provider": self.llm_provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "notes": self.notes,
        }


class _RecordSlot:
    """Mutable object the caller receives from ``with trace.record(...) as slot``.

    The caller may set any of the public attributes during the block; they will
    be merged into the final ``AgentTraceRecord`` on ``__exit__``.
    """

    def __init__(self) -> None:
        self.output_summary: str = ""
        self.llm_provider: str | None = None
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.notes: str = ""


# ---------------------------------------------------------------------------
# TraceCollector
# ---------------------------------------------------------------------------


class TraceCollector:
    """Collects per-agent timing and metadata across a full pipeline run.

    Usage
    -----
    ::

        trace = TraceCollector()

        with trace.record("collector", agent_type="rule", input_summary="tx 0xabc") as slot:
            result = collect_transaction_artifacts(...)
            slot.output_summary = f"{len(result['transactions'])} txs collected"

        with trace.record("evidence_extractor", agent_type="llm") as slot:
            evidence = run_llm_evidence_extractor(...)
            slot.output_summary = f"{len(evidence.get('evidence_items', []))} items"
            slot.notes = "tokens: not captured (response parsed internally)"
    """

    def __init__(self) -> None:
        self.records: list[AgentTraceRecord] = []
        self.revision_triggered: bool = False
        self.revision_critique: str | None = None
        self.qa_retry_triggered: bool = False
        self.qa_retry_critique: str | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def record(
        self,
        agent_name: str,
        agent_type: str = "rule",
        input_summary: str = "",
        notes: str = "",
    ) -> Generator[_RecordSlot, None, None]:
        """Context manager that times the enclosed block and appends a record.

        Yields a ``_RecordSlot`` the caller can populate with output details.
        If an exception propagates out of the block the record is still
        appended (with ``[errored]`` appended to *notes*) and the exception
        is re-raised.
        """
        started_at = _utc_iso()
        t0 = time.perf_counter()
        slot = _RecordSlot()
        slot.notes = notes
        errored = False
        try:
            yield slot
        except Exception:
            errored = True
            raise
        finally:
            duration_ms = max(0, round((time.perf_counter() - t0) * 1000))
            final_notes = slot.notes
            if errored:
                final_notes = (final_notes + " [errored]").strip()
            self.records.append(
                AgentTraceRecord(
                    agent_name=agent_name,
                    agent_type=agent_type,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    input_summary=input_summary,
                    output_summary=slot.output_summary,
                    llm_provider=slot.llm_provider,
                    prompt_tokens=slot.prompt_tokens,
                    completion_tokens=slot.completion_tokens,
                    notes=final_notes,
                )
            )

    # ------------------------------------------------------------------
    # Loop flags
    # ------------------------------------------------------------------

    def set_revision(self, critique: str) -> None:
        """Mark that the Validator → Reasoner revision loop fired."""
        self.revision_triggered = True
        self.revision_critique = critique

    def set_qa_retry(self, critique: str) -> None:
        """Mark that the QA retry loop fired."""
        self.qa_retry_triggered = True
        self.qa_retry_critique = critique

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return the ``pipeline_trace`` dict matching the frontend schema."""
        return {
            "revision_triggered": self.revision_triggered,
            "revision_critique": self.revision_critique,
            "qa_retry_triggered": self.qa_retry_triggered,
            "qa_retry_critique": self.qa_retry_critique,
            "records": [r.to_dict() for r in self.records],
        }

    def to_markdown(self) -> str:
        """Return a human-readable pipeline timeline for GitHub / code review.

        Format
        ------
        - One bullet per agent with timing
        - Indented sub-bullets for LLM details (provider + token counts)
        - Callout banners when revision or QA-retry loops fired
        """
        lines: list[str] = []
        lines.append("# Pipeline Trace")
        lines.append("")

        # Summary table header
        lines.append("## Run Summary")
        lines.append("")
        lines.append(f"- **Agents recorded**: {len(self.records)}")
        total_ms = sum(r.duration_ms for r in self.records)
        lines.append(f"- **Total wall time**: {total_ms:,} ms ({total_ms / 1000:.2f} s)")
        lines.append(f"- **Revision loop**: {'✓ triggered' if self.revision_triggered else '✗ not triggered'}")
        lines.append(f"- **QA retry loop**: {'✓ triggered' if self.qa_retry_triggered else '✗ not triggered'}")
        lines.append("")

        if self.revision_triggered and self.revision_critique:
            lines.append("> **Revision critique** (Validator → Reasoner):")
            lines.append(f"> {self.revision_critique[:300]}")
            lines.append("")

        if self.qa_retry_triggered and self.qa_retry_critique:
            lines.append("> **QA retry critique** (Quality Assessor → Evidence Extractor):")
            lines.append(f"> {self.qa_retry_critique[:300]}")
            lines.append("")

        lines.append("## Agent Timeline")
        lines.append("")

        for i, r in enumerate(self.records, start=1):
            type_badge = "[LLM]" if r.agent_type == "llm" else "[rule]"
            lines.append(f"### {i}. `{r.agent_name}` {type_badge}")
            lines.append("")
            lines.append(f"- **Started**: `{r.started_at}`")
            lines.append(f"- **Duration**: {r.duration_ms:,} ms")
            if r.input_summary:
                lines.append(f"- **Input**: {r.input_summary}")
            if r.output_summary:
                lines.append(f"- **Output**: {r.output_summary}")
            if r.agent_type == "llm":
                provider_str = r.llm_provider or "unknown"
                lines.append(f"- **LLM provider**: {provider_str}")
                if r.prompt_tokens is not None or r.completion_tokens is not None:
                    pt = r.prompt_tokens if r.prompt_tokens is not None else "?"
                    ct = r.completion_tokens if r.completion_tokens is not None else "?"
                    lines.append(f"- **Tokens**: prompt={pt}, completion={ct}")
            if r.notes:
                lines.append(f"- **Notes**: {r.notes}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Null / no-op fallback
# ---------------------------------------------------------------------------


class _NullRecordSlot:
    """Slot returned by the null trace — writes to it are silently discarded."""

    output_summary: str = ""
    llm_provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    notes: str = ""


class _NullTraceCollector:
    """Drop-in replacement for TraceCollector that does nothing.

    Use ``null_trace()`` to obtain one.  Callers do **not** need ``if trace``
    guards — every method on this class is a safe no-op.
    """

    records: list = []
    revision_triggered: bool = False
    revision_critique: str | None = None
    qa_retry_triggered: bool = False
    qa_retry_critique: str | None = None

    @contextmanager
    def record(
        self,
        agent_name: str,
        agent_type: str = "rule",
        input_summary: str = "",
        notes: str = "",
    ) -> Generator[_NullRecordSlot, None, None]:
        yield _NullRecordSlot()

    def set_revision(self, critique: str) -> None:  # noqa: ARG002
        pass

    def set_qa_retry(self, critique: str) -> None:  # noqa: ARG002
        pass

    def to_dict(self) -> dict:
        return {
            "revision_triggered": False,
            "revision_critique": None,
            "qa_retry_triggered": False,
            "qa_retry_critique": None,
            "records": [],
        }

    def to_markdown(self) -> str:
        return "# Pipeline Trace\n\n*(no-op trace — nothing recorded)*\n"


def null_trace() -> _NullTraceCollector:
    """Return a no-op TraceCollector that records nothing.

    Useful when a caller wants to skip tracing without littering
    ``if trace is not None`` checks throughout the code.
    """
    return _NullTraceCollector()

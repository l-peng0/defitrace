import { useEffect, useState } from 'react'
import { fetchTrace } from '../api/client'
import type { TraceResponse, AgentStep } from '../api/types'

const AGENT_COLOR: Record<string, string> = {
  source_finder:         'var(--accent-cyan)',
  source_expander:       'var(--accent-cyan)',
  evidence_normalizer:   'var(--accent-blue)',
  technical_validation:  'var(--accent-amber)',
  llm_timeline_synthesizer: 'var(--accent-blue)',
  llm_narrative_writer:  'var(--accent-blue)',
  dossier_assembler:     'var(--accent-green)',
  quality_judge:         'var(--accent-green)',
}

function statusBadge(status: string) {
  const colors: Record<string, { bg: string; text: string }> = {
    completed: { bg: 'var(--accent-green)22', text: 'var(--accent-green)' },
    failed:    { bg: 'var(--accent-red)22',   text: 'var(--accent-red)' },
    running:   { bg: 'var(--accent-amber)22', text: 'var(--accent-amber)' },
  }
  const c = colors[status] ?? { bg: 'var(--bg-elevated)', text: 'var(--text-muted)' }
  return (
    <span style={{
      fontSize: '0.6rem',
      fontWeight: 700,
      padding: '1px 6px',
      borderRadius: 3,
      background: c.bg,
      color: c.text,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
    }}>
      {status}
    </span>
  )
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function MetricChips({ metrics }: { metrics?: Record<string, unknown> }) {
  if (!metrics || Object.keys(metrics).length === 0) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
      {Object.entries(metrics).map(([k, v]) => (
        <span key={k} style={{
          fontSize: '0.6rem',
          padding: '1px 6px',
          borderRadius: 3,
          background: 'var(--bg-base)',
          color: 'var(--text-muted)',
          border: '1px solid var(--border)',
        }}>
          {k.replace(/_/g, ' ')}: <strong style={{ color: 'var(--text-primary)' }}>{String(v)}</strong>
        </span>
      ))}
    </div>
  )
}

function AgentRow({ step, maxElapsed }: { step: AgentStep; maxElapsed: number }) {
  const color = AGENT_COLOR[step.agent_id] ?? 'var(--accent-blue)'
  const barWidth = maxElapsed > 0 && step.elapsed_ms
    ? Math.max(2, Math.round((step.elapsed_ms / maxElapsed) * 100))
    : 0

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      padding: '0.65rem 0.9rem',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
    }}>
      {/* Top row: name + status + time */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          display: 'inline-block',
        }} />
        <span style={{
          fontSize: '0.8rem',
          fontWeight: 600,
          color: 'var(--text-primary)',
          flex: 1,
          minWidth: 0,
        }}>
          {step.agent_name}
        </span>
        {statusBadge(step.status)}
        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: 'auto', flexShrink: 0 }}>
          {fmtMs(step.elapsed_ms)}
        </span>
      </div>

      {/* Duration bar */}
      {barWidth > 0 && (
        <div style={{
          height: 3,
          background: 'var(--bg-elevated)',
          borderRadius: 2,
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${barWidth}%`,
            background: color,
            borderRadius: 2,
            opacity: 0.7,
          }} />
        </div>
      )}

      {/* Metrics */}
      <MetricChips metrics={step.metrics} />

      {step.note && (
        <p style={{ margin: 0, fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {step.note}
        </p>
      )}
    </div>
  )
}

interface Props {
  incidentId: string
}

export default function AgentTrace({ incidentId }: Props) {
  const [trace, setTrace] = useState<TraceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchTrace(incidentId)
      .then(setTrace)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [incidentId])

  if (loading) return (
    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading agent trace…</p>
  )
  if (error) return (
    <p style={{ color: 'var(--accent-red)', fontSize: '0.85rem' }}>Failed to load trace: {error}</p>
  )
  if (!trace || trace.agents.length === 0) return (
    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No agent trace available for this incident.</p>
  )

  const maxElapsed = Math.max(...trace.agents.map(a => a.elapsed_ms ?? 0))
  const totalSec = trace.total_elapsed_ms != null
    ? `${(trace.total_elapsed_ms / 1000).toFixed(1)}s`
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Summary strip */}
      <div style={{
        display: 'flex',
        gap: 16,
        padding: '0.6rem 0.9rem',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>{trace.agents.length}</strong> agents
        </span>
        {totalSec && (
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            total <strong style={{ color: 'var(--text-primary)' }}>{totalSec}</strong>
          </span>
        )}
        {trace.current_stage && (
          <span style={{ fontSize: '0.7rem', color: 'var(--accent-amber)' }}>
            stage: {trace.current_stage}
          </span>
        )}
      </div>

      {/* Agent rows */}
      {trace.agents.map((step, idx) => (
        <AgentRow key={step.agent_id ?? idx} step={step} maxElapsed={maxElapsed} />
      ))}
    </div>
  )
}

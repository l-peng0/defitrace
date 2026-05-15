import { useState } from 'react'
import type { IncidentEntry } from '../api/types'

interface Props {
  incidents: IncidentEntry[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function scoreColor(score: number): string {
  if (score >= 0.6) return 'var(--accent-green)'
  if (score >= 0.3) return 'var(--accent-amber)'
  return 'var(--accent-red)'
}

export default function IncidentSidebar({ incidents, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState('')

  const filtered = incidents.filter(inc => {
    if (!query) return true
    const q = query.toLowerCase()
    return (
      inc.incident_id.toLowerCase().includes(q) ||
      inc.title.toLowerCase().includes(q) ||
      (inc.protocol_name ?? '').toLowerCase().includes(q)
    )
  })

  return (
    <aside
      style={{
        width: 220,
        minWidth: 220,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '1rem 0.75rem 0.5rem',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: '0.65rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--accent-cyan)',
            marginBottom: 4,
          }}
        >
          DeFiTrace
        </p>
        <p
          style={{
            margin: 0,
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
          }}
        >
          {incidents.length} incidents
        </p>
      </div>

      {/* Filter input */}
      <div style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Filter incidents…"
          style={{
            width: '100%',
            boxSizing: 'border-box',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            color: 'var(--text-primary)',
            fontSize: '0.75rem',
            padding: '0.35rem 0.5rem',
            outline: 'none',
          }}
        />
      </div>

      {/* Scrollable list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filtered.length === 0 && (
          <p
            style={{
              padding: '1rem 0.75rem',
              color: 'var(--text-muted)',
              fontSize: '0.75rem',
              margin: 0,
            }}
          >
            No matches
          </p>
        )}
        {filtered.map(inc => {
          const isSelected = inc.incident_id === selectedId
          const color = scoreColor(inc.completeness_score ?? 0)

          return (
            <button
              key={inc.incident_id}
              onClick={() => onSelect(inc.incident_id)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                border: 'none',
                borderLeft: isSelected ? '3px solid var(--accent-blue)' : '3px solid transparent',
                borderBottom: '1px solid var(--border)',
                padding: '0.6rem 0.75rem',
                cursor: 'pointer',
                transition: 'background 0.15s',
              }}
            >
              {/* Protocol name */}
              <div
                style={{
                  fontWeight: 600,
                  fontSize: '0.78rem',
                  color: 'var(--text-primary)',
                  marginBottom: 2,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {inc.protocol_name || inc.title}
              </div>

              {/* Chain + date row */}
              <div
                style={{
                  display: 'flex',
                  gap: 6,
                  alignItems: 'center',
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    fontSize: '0.65rem',
                    color: 'var(--text-muted)',
                    textTransform: 'capitalize',
                  }}
                >
                  {inc.chain}
                </span>
                <span style={{ color: 'var(--border)', fontSize: '0.65rem' }}>·</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                  {inc.incident_date}
                </span>
              </div>

              {/* Score chip */}
              <span
                style={{
                  display: 'inline-block',
                  fontSize: '0.6rem',
                  fontWeight: 700,
                  padding: '1px 6px',
                  borderRadius: 3,
                  background: color + '22',
                  color: color,
                  border: `1px solid ${color}55`,
                  letterSpacing: '0.04em',
                }}
              >
                {Math.round((inc.completeness_score ?? 0) * 100)}% complete
              </span>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

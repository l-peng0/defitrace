import * as Tabs from '@radix-ui/react-tabs'
import type { IncidentBundle } from '../api/types'
import AgentTrace from './AgentTrace'

interface Props {
  bundle: IncidentBundle
}

/* ── small helpers ──────────────────────────────────────────── */

function scoreColor(score: number): string {
  if (score >= 0.6) return 'var(--accent-green)'
  if (score >= 0.3) return 'var(--accent-amber)'
  return 'var(--accent-red)'
}

function StatCard({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string | number
  valueColor?: string
}) {
  return (
    <div
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '0.75rem 1rem',
        minWidth: 120,
        flex: 1,
      }}
    >
      <div
        style={{
          fontSize: '0.6rem',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'var(--text-muted)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: '1.1rem',
          fontWeight: 700,
          color: valueColor ?? 'var(--text-primary)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

/* ── tab content components ────────────────────────────────── */

function OverviewTab({ bundle }: { bundle: IncidentBundle }) {
  const overview = bundle.analyst_report?.case_overview
  const qr = bundle.quality_report
  const ai = bundle.augmented_incident

  const score = qr?.completeness_score ?? 0
  const color = scoreColor(score)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* HeroStrip — 4 stat cards */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <StatCard
          label="Analysis Completeness"
          value={`${Math.round(score * 100)}%`}
          valueColor={color}
        />
        <StatCard label="Sources" value={qr?.source_count ?? '—'} />
        <StatCard
          label="Chain"
          value={ai?.chain ?? '—'}
          valueColor="var(--accent-cyan)"
        />
        <StatCard
          label="Pattern"
          value={
            ai?.pattern_hypotheses?.[0]?.label ??
            bundle.incident_library_entry?.pattern_label ??
            '—'
          }
        />
      </div>

      {/* Headline */}
      {overview?.headline && (
        <h2
          style={{
            margin: 0,
            fontSize: '1.1rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            lineHeight: 1.4,
          }}
        >
          {overview.headline}
        </h2>
      )}

      {/* What happened */}
      {(overview?.what_happened ?? ai?.summary) && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '1rem',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: '0.82rem',
              color: 'var(--text-muted)',
              lineHeight: 1.7,
            }}
          >
            {overview?.what_happened ?? ai?.summary}
          </p>
        </div>
      )}

      {/* Missing fields notice */}
      {qr?.missing_fields && qr.missing_fields.length > 0 && (
        <div
          style={{
            background: 'var(--accent-amber)11',
            border: '1px solid var(--accent-amber)44',
            borderRadius: 6,
            padding: '0.75rem 1rem',
          }}
        >
          <p
            style={{
              margin: '0 0 0.4rem',
              fontSize: '0.7rem',
              fontWeight: 700,
              color: 'var(--accent-amber)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Missing fields
          </p>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {qr.missing_fields.join(' · ')}
          </p>
        </div>
      )}
    </div>
  )
}

function shortAddr(a: string | undefined): string {
  if (!a) return ''
  return a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a
}

function AnalysisTab({ bundle }: { bundle: IncidentBundle }) {
  const ar = bundle.analyst_report
  const profile = ar?.attacker_profile
  const v2 = bundle.attacker_profile_v2
  const v2Fields = v2?.fields
  const exploitPath = ar?.exploit_path ?? []
  const transfers = v2Fields?.post_attack_fund_flow?.transfers ?? []
  // Prefer v2 (ExternalExplorer-grounded) over v1 (LLM-only)
  const netProfitUsd = v2Fields?.net_profit_usd?.value ?? profile?.profit_usd
  const fundingSourceText =
    v2Fields?.funding_source?.summary ?? v2Fields?.funding_source?.source ?? profile?.funding_source
  const profitTopToken = v2Fields?.net_profit_usd?.tokens?.[0]
  const profitTokensText = profitTopToken
    ? `${profitTopToken.amount ?? ''} ${profitTopToken.symbol ?? ''}`.trim()
    : profile?.profit_tokens
  const deploymentDuration = v2Fields?.deployment_to_exploit_time?.human
  const preAttack = v2Fields?.pre_attack_activity?.summary
  const techniques = v2?.techniques ?? profile?.techniques

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Attacker Profile Card */}
      <section>
        <h3
          style={{
            margin: '0 0 0.75rem',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--accent-cyan)',
          }}
        >
          Attacker Profile
        </h3>
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '1rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.75rem',
          }}
        >
          {v2 || profile ? (
            <>
              {v2?.attacker_address && (
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Attacker EOA
                  </div>
                  <code style={{ fontSize: '0.78rem', color: 'var(--text-primary)' }}>
                    {shortAddr(v2.attacker_address)}
                  </code>
                </div>
              )}
              {fundingSourceText && (
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Funding Source
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                    {fundingSourceText}
                  </div>
                </div>
              )}
              {netProfitUsd != null && (
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Net Profit (USD){v2Fields?.net_profit_usd?.value != null && (
                      <span style={{ marginLeft: 6, fontSize: '0.55rem', color: 'var(--accent-cyan)', letterSpacing: 0 }}>
                        on-chain
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.95rem', color: 'var(--accent-green)', fontWeight: 700 }}>
                    ${netProfitUsd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </div>
                </div>
              )}
              {profitTokensText && (
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Profit (Tokens)
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                    {profitTokensText}
                  </div>
                </div>
              )}
              {deploymentDuration && (
                <div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Deployment → Exploit
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                    {deploymentDuration}
                  </div>
                </div>
              )}
              {preAttack && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>
                    Pre-Attack Activity
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {preAttack}
                  </div>
                </div>
              )}
              {techniques && techniques.length > 0 && (
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                    Techniques
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {techniques.map((t, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.65rem',
                          padding: '2px 8px',
                          borderRadius: 3,
                          background: 'var(--accent-blue)22',
                          color: 'var(--accent-blue)',
                          border: '1px solid var(--accent-blue)44',
                        }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Attacker profile data not available for this incident.
            </p>
          )}
        </div>
      </section>

      {/* Fund Flow (on-chain transfers) */}
      {transfers.length > 0 && (
        <section>
          <h3
            style={{
              margin: '0 0 0.75rem',
              fontSize: '0.75rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--accent-cyan)',
            }}
          >
            Fund Flow
            <span style={{ marginLeft: 8, fontSize: '0.55rem', color: 'var(--accent-cyan)', letterSpacing: 0, textTransform: 'none' }}>
              on-chain
            </span>
          </h3>
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '0.5rem',
              overflow: 'auto',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                  <th style={{ padding: '4px 8px', fontWeight: 600 }}>From</th>
                  <th style={{ padding: '4px 8px', fontWeight: 600 }}>To</th>
                  <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>Amount</th>
                  <th style={{ padding: '4px 8px', fontWeight: 600 }}>Token</th>
                  <th style={{ padding: '4px 8px', fontWeight: 600, textAlign: 'right' }}>USD</th>
                </tr>
              </thead>
              <tbody>
                {transfers.slice(0, 30).map((t, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '4px 8px' }}>
                      <code style={{ color: 'var(--text-secondary)' }}>{shortAddr(t.from)}</code>
                    </td>
                    <td style={{ padding: '4px 8px' }}>
                      <code style={{ color: 'var(--text-secondary)' }}>{shortAddr(t.to)}</code>
                    </td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', color: 'var(--text-primary)' }}>
                      {t.amount ?? '—'}
                    </td>
                    <td style={{ padding: '4px 8px', color: 'var(--text-secondary)' }}>
                      {t.symbol ?? ''}
                    </td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', color: t.value_usd ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                      {t.value_usd ? `$${t.value_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {transfers.length > 30 && (
              <div style={{ padding: '6px 8px', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                Showing 30 of {transfers.length} transfers.
              </div>
            )}
          </div>
        </section>
      )}

      {/* Exploit Path */}
      <section>
        <h3
          style={{
            margin: '0 0 0.75rem',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: 'var(--accent-cyan)',
          }}
        >
          Exploit Path
        </h3>
        {exploitPath.length === 0 ? (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
            Exploit path data not available for this incident.
          </p>
        ) : (
          <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {exploitPath.map((step, idx) => (
              <li
                key={idx}
                style={{
                  display: 'flex',
                  gap: '0.75rem',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '0.75rem 1rem',
                  alignItems: 'flex-start',
                }}
              >
                {/* Step number */}
                <span
                  style={{
                    minWidth: 24,
                    height: 24,
                    borderRadius: '50%',
                    background: 'var(--accent-blue)33',
                    color: 'var(--accent-blue)',
                    border: '1px solid var(--accent-blue)55',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {step.step ?? idx + 1}
                </span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', marginBottom: 4 }}>
                    {step.action}
                  </div>
                  {step.contracts && step.contracts.length > 0 && (
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'monospace', marginBottom: 2 }}>
                      {step.contracts.join(', ')}
                    </div>
                  )}
                  {step.tx_hash && (
                    <div style={{ fontSize: '0.65rem', color: 'var(--accent-blue)', fontFamily: 'monospace' }}>
                      {step.tx_hash.slice(0, 18)}…
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}

function PipelineTab({ incidentId }: { incidentId: string }) {
  return <AgentTrace incidentId={incidentId} />
}

/* ── main component ─────────────────────────────────────────── */

const TAB_TRIGGER_STYLE: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderBottom: '2px solid transparent',
  padding: '0.5rem 1rem',
  fontSize: '0.78rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  letterSpacing: '0.04em',
  transition: 'color 0.15s, border-color 0.15s',
}

const TAB_TRIGGER_ACTIVE_STYLE: React.CSSProperties = {
  ...TAB_TRIGGER_STYLE,
  color: 'var(--accent-blue)',
  borderBottom: '2px solid var(--accent-blue)',
}

export default function IncidentDetail({ bundle }: Props) {
  const ai = bundle.augmented_incident
  const incidentId = ai.incident_id
  const title =
    bundle.analyst_report?.case_overview?.headline ??
    bundle.incident_library_entry?.title ??
    ai.title

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Page title */}
      <div style={{ marginBottom: '1.25rem' }}>
        <p
          style={{
            margin: '0 0 4px',
            fontSize: '0.65rem',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: 'var(--accent-cyan)',
          }}
        >
          {ai.chain} · {bundle.incident_library_entry?.incident_date ?? ai.incident_id}
        </p>
        <h1
          style={{
            margin: 0,
            fontSize: '1.3rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            lineHeight: 1.3,
          }}
        >
          {title}
        </h1>
      </div>

      {/* Tabs */}
      <Tabs.Root defaultValue="overview">
        <Tabs.List
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border)',
            marginBottom: '1.5rem',
            gap: 0,
          }}
        >
          <Tabs.Trigger
            value="overview"
            style={TAB_TRIGGER_STYLE}
            onMouseEnter={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'
              }
            }}
            onMouseLeave={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'
              }
            }}
          >
            Overview
          </Tabs.Trigger>
          <Tabs.Trigger
            value="analysis"
            style={TAB_TRIGGER_STYLE}
            onMouseEnter={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'
              }
            }}
            onMouseLeave={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'
              }
            }}
          >
            Analysis
          </Tabs.Trigger>
          <Tabs.Trigger
            value="pipeline"
            style={TAB_TRIGGER_STYLE}
            onMouseEnter={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-primary)'
              }
            }}
            onMouseLeave={e => {
              if (!(e.currentTarget as HTMLElement).getAttribute('data-state')?.includes('active')) {
                (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'
              }
            }}
          >
            Pipeline
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="overview">
          <OverviewTab bundle={bundle} />
        </Tabs.Content>
        <Tabs.Content value="analysis">
          <AnalysisTab bundle={bundle} />
        </Tabs.Content>
        <Tabs.Content value="pipeline">
          <PipelineTab incidentId={incidentId} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}

/* override active tab style via data-state — inject a global style block */
// We use a style injection approach for Radix data-state selectors
// since inline styles can't target pseudo-attributes.
const _styleEl =
  typeof document !== 'undefined' &&
  (() => {
    const el = document.createElement('style')
    el.textContent = `
      [data-radix-tabs-trigger][data-state="active"] {
        color: var(--accent-blue) !important;
        border-bottom: 2px solid var(--accent-blue) !important;
      }
    `
    document.head.appendChild(el)
    return el
  })()

void _styleEl
void TAB_TRIGGER_ACTIVE_STYLE

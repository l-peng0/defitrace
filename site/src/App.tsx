import { useState, useEffect } from 'react'
import { fetchIncidents } from './api/client'
import type { IncidentEntry, IncidentBundle } from './api/types'
import { fetchBundle } from './api/client'
import IncidentSidebar from './components/IncidentSidebar'
import IncidentDetail from './components/IncidentDetail'

export default function App() {
  const [incidents, setIncidents] = useState<IncidentEntry[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [bundle, setBundle] = useState<IncidentBundle | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchIncidents().then(r => {
      setIncidents(r.incidents || [])
      if (r.incidents?.length > 0 && !selectedId) {
        setSelectedId(r.incidents[0].incident_id)
      }
    }).catch(console.error)
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    fetchBundle(selectedId)
      .then(setBundle)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedId])

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-base)' }}>
      <IncidentSidebar
        incidents={incidents}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      <main style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }}>
        {loading && <p style={{ color: 'var(--text-muted)' }}>Loading…</p>}
        {!loading && bundle && <IncidentDetail bundle={bundle} />}
      </main>
    </div>
  )
}

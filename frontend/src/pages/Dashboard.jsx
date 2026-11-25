import React, { useEffect, useState } from 'react'
import { api } from '../services/api.js'

export default function Dashboard() {
  const [analytics, setAnalytics] = useState(null)
  const [insights, setInsights] = useState(null)
  const [pipeline, setPipeline] = useState(null)
  const [upcoming, setUpcoming] = useState(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('live')
  const [view, setView] = useState('overview')   // 'overview' | 'pipeline' | 'appointments'

  useEffect(() => {
    Promise.all([
      api('/analytics').then(a => {
        setAnalytics(a)
        if (!a?.live?.calls && a?.demo?.calls) setMode('demo')
      }).catch(() => {}),
      api('/crm/insights').then(setInsights).catch(() => {}),
      api('/crm/pipeline').then(setPipeline).catch(() => {}),
      api('/appointments/next-slots').then(setUpcoming).catch(() => {}),
    ]).catch(e => setError(e.message))
  }, [])

  const metrics = analytics?.[mode]

  return (
    <>
      <header className="page-heading">
        <div><h1>Sales dashboard</h1><p>Lead pipeline, booking calendar, and business insights.</p></div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {['overview', 'pipeline', 'appointments'].map(v => (
            <button key={v} className={view === v ? 'primary' : 'secondary'} onClick={() => setView(v)}>
              {v === 'overview' ? '📊 Overview' : v === 'pipeline' ? '🏆 Pipeline' : '📅 Appointments'}
            </button>
          ))}
        </div>
      </header>
      {error && <p className="error">{error}</p>}

      {/* ── Overview ── */}
      {view === 'overview' && (
        <>
          {/* CRM insights row */}
          {insights && (
            <div className="metrics" style={{ marginBottom: 16 }}>
              {[
                ['Total calls', insights.total_calls],
                ['Qualified leads', insights.total_leads],
                ['Hot leads', insights.hot],
                ['Warm leads', insights.warm],
                ['Avg score', insights.avg_score],
                ['Demos booked', insights.appointments_booked],
                ['Upcoming demos', insights.appointments_upcoming],
                ['Avg call (s)', insights.avg_call_duration_secs],
              ].map(([label, value]) => (
                <section className="card metric" key={label}>
                  <span>{label}</span><strong>{value ?? '—'}</strong>
                </section>
              ))}
            </div>
          )}

          {/* per-mode breakdown */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 10, alignItems: 'center' }}>
            <label>Session type&nbsp;
              <select value={mode} onChange={e => setMode(e.target.value)}>
                <option value="demo">Text demo</option>
                <option value="live">Live voice</option>
              </select>
            </label>
          </div>
          {metrics && (
            <div className="metrics">
              <Breakdown title="Lead distribution" values={metrics.leads} />
              <Breakdown title="Customer sentiment" values={metrics.sentiment} />
              <Breakdown title="Top objections" values={metrics.objections} />
            </div>
          )}
        </>
      )}

      {/* ── Pipeline ── */}
      {view === 'pipeline' && (
        <div className="pipeline-grid">
          {pipeline?.length === 0 && <p className="hint">No leads yet. Complete a call to see leads here.</p>}
          {pipeline?.map(lead => (
            <div className="card pipeline-card" key={lead.call_id}>
              <div className="pipeline-header">
                <strong>{lead.details?.name || 'Unknown'}</strong>
                <span className={`badge badge-${(lead.status || '').toLowerCase()}`}>{lead.status} · {lead.score}/100</span>
              </div>
              <dl className="pipeline-dl">
                {lead.details?.company && <><dt>Company</dt><dd>{lead.details.company}</dd></>}
                {lead.details?.budget && <><dt>Budget</dt><dd>₹{lead.details.budget}</dd></>}
                {lead.details?.need && <><dt>Need</dt><dd>{lead.details.need}</dd></>}
                {lead.details?.timeline && <><dt>Timeline</dt><dd>{lead.details.timeline}</dd></>}
              </dl>
              {lead.summary && <p className="hint" style={{ marginTop: 8 }}>{lead.summary}</p>}
              {lead.appointments > 0 && <p className="appt-badge">📅 {lead.appointments} appointment{lead.appointments > 1 ? 's' : ''} booked</p>}
              {lead.next_action && <p className="hint">→ {lead.next_action}</p>}
              <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {lead.objections?.map(o => <span key={o} className="badge" style={{ background: '#ffe8ed', color: '#a21b35' }}>{o}</span>)}
                <span className="badge" style={{ background: '#f0f4ff', color: '#3a4a7a' }}>{lead.sentiment}</span>
                {lead.mode === 'live' && <span className="badge">🎙 Live</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Appointments ── */}
      {view === 'appointments' && (
        <>
          <h2 style={{ marginBottom: 14 }}>Upcoming open slots</h2>
          <div className="metrics">
            {upcoming?.map(s => (
              <section className="card metric" key={s.date}>
                <span>{new Date(s.date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                <strong>{s.available} slots</strong>
                <small style={{ color: '#59657e' }}>First: {s.first_slot}</small>
              </section>
            ))}
          </div>
          <ApptList />
        </>
      )}
    </>
  )
}

function Breakdown({ title, values }) {
  const entries = Object.entries(values || {}).sort((a, b) => b[1] - a[1])
  return (
    <section className="card breakdown"><h2>{title}</h2>
      {entries.length ? entries.map(([label, value]) => (
        <div key={label} className="bar-row">
          <div><span>{label}</span><strong>{value}</strong></div>
          <progress aria-label={label} value={value} max={entries[0][1]} />
        </div>
      )) : <p className="hint">No data yet.</p>}
    </section>
  )
}

function ApptList() {
  const [appts, setAppts] = useState(null)
  useEffect(() => { api('/appointments').then(setAppts).catch(() => {}) }, [])
  if (!appts) return null
  if (!appts.length) return <p className="hint" style={{ marginTop: 14 }}>No upcoming appointments booked yet.</p>
  return (
    <div style={{ marginTop: 20 }}>
      <h2 style={{ marginBottom: 10 }}>Booked appointments</h2>
      <div className="pipeline-grid">
        {appts.map(a => (
          <div className="card pipeline-card" key={a.id}>
            <div className="pipeline-header">
              <strong>{a.name}</strong>
              <span className="badge" style={{ background: '#e8f5e9', color: '#2e7d32' }}>{a.status}</span>
            </div>
            <dl className="pipeline-dl">
              <dt>Date</dt><dd>{a.date} at {a.time}</dd>
              {a.email && <><dt>Email</dt><dd>{a.email}</dd></>}
              {a.phone && <><dt>Phone</dt><dd>{a.phone}</dd></>}
              {a.notes && <><dt>Notes</dt><dd>{a.notes}</dd></>}
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}

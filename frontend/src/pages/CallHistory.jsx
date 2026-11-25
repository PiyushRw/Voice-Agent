import React, { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { Transcript } from './VoiceCall.jsx'

export default function CallHistory() {
  const [rows, setRows] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    const update = () => api('/calls').then(items => { if (mounted) setRows(items) }).catch(e => { if (mounted) setError(e.message) })
    update()
    const timer = setInterval(update, 3000)
    return () => { mounted = false; clearInterval(timer) }
  }, [])

  async function select(id) {
    setError('')
    try { setSelected(await api('/calls/' + id)) } catch (e) { setError(e.message) }
  }

  return (
    <>
      <header className="page-heading">
        <div><h1>Call history</h1><p>Review transcripts, qualification, and follow-up details.</p></div>
      </header>
      {error && <p className="error">{error}</p>}
      <div className="history-layout">
        <section className="card call-list">
          <h2>Sessions</h2>
          {rows?.length === 0 && <p className="hint">Start a session in the call console.</p>}
          {rows?.map(row => (
            <button key={row.id} className={selected?.id === row.id ? 'active' : ''} onClick={() => select(row.id)}>
              <strong>{row.name || (row.mode === 'live' ? '🎙 Voice call' : '💬 Text demo')}</strong>
              <span>{new Date(row.started).toLocaleString()} · {row.ended ? row.status || 'Completed' : '🔴 In progress'}</span>
            </button>
          ))}
        </section>

        <section className="card transcript">
          <div className="section-title"><h2>Call details</h2></div>
          {selected ? (
            <>
              {selected.lead && (
                <div className="lead">
                  <span>Lead · {selected.lead.score}/100 · {selected.lead.status}</span>
                  <dl>{Object.entries(selected.lead.details || {}).filter(([k]) => k !== 'notes').map(([k, v]) => (
                    <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
                  ))}</dl>
                </div>
              )}
              {selected.analysis && (
                <div className="lead">
                  <strong>{selected.analysis.outcome} · {selected.analysis.sentiment}</strong>
                  <p>{selected.analysis.summary}</p>
                  {selected.analysis.objections?.length > 0 && <p>Objections · {selected.analysis.objections.join(', ')}</p>}
                  <p className="hint">→ {selected.analysis.next_action}</p>
                </div>
              )}
              {selected.appointments?.length > 0 && (
                <div className="lead appt-confirmed">
                  <span>📅 Appointments</span>
                  {selected.appointments.map(a => (
                    <div key={a.id}><strong>{a.date} at {a.time}</strong> · <em>{a.status}</em>
                      {a.notes && <p className="hint">{a.notes}</p>}
                    </div>
                  ))}
                </div>
              )}
              <Transcript messages={selected.messages} />
            </>
          ) : <p className="empty">Select a session to review its details.</p>}
        </section>
      </div>
    </>
  )
}

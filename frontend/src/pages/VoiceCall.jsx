import React, { useEffect, useRef, useState } from 'react'
import { Room, RoomEvent, Track } from 'livekit-client'
import { api } from '../services/api.js'

const GREETING = "Hi there! I'm Maya from FlowCRM. How can I help you today?"

const suggestions = [
  ['Share requirements', 'My name is Rahul, I need a CRM for 20 people, my budget is 6000, I am the decision maker, and I need it within 30 days.'],
  ['Ask about pricing', 'What is the pricing for Professional?'],
  ['Book a demo', 'Can you schedule a demo for me tomorrow?'],
  ['Share an objection', 'Professional is too expensive for us.'],
]

export function Transcript({ messages, typing }) {
  const bottom = useRef(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, typing])
  return (
    <div className="messages" aria-live="polite">
      {messages.length === 0
        ? <div className="empty">The transcript will appear here when the session starts.</div>
        : messages.map((item, index) => (
            <article key={index} className={'message ' + item.role}>
              <span>
                {item.role === 'user' ? 'Customer' : 'FlowCRM'}
                {item.interrupted ? ' · Interrupted' : ''}
                {item.language && item.language !== 'en' ? ` · ${item.language.toUpperCase()}` : ''}
              </span>
              <p>{item.content}</p>
            </article>
          ))
      }
      {typing && (
        <article className="message assistant typing-indicator" aria-label="Agent is thinking">
          <span>FlowCRM</span>
          <p><span className="dot"/><span className="dot"/><span className="dot"/></p>
        </article>
      )}
      <div ref={bottom}/>
    </div>
  )
}

export default function VoiceCall() {
  const [call, setCall] = useState(null)
  const [detail, setDetail] = useState(null)
  const [live, setLive] = useState(false)
  const [text, setText] = useState('')
  const [status, setStatus] = useState('Ready')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [typing, setTyping] = useState(false)
  const [muted, setMuted] = useState(false)
  const [sources, setSources] = useState([])
  const [appointment, setAppointment] = useState(null)
  const room = useRef(null)
  const active = useRef(false)
  const audio = useRef(null)

  useEffect(() => {
    api('/health').then(d => setLive(d.live)).catch(e => setError(e.message))
    return () => { room.current?.disconnect() }
  }, [])

  useEffect(() => {
    if (!call || detail?.ended) return
    let current = true
    const load = () => api('/calls/' + call.id).then(v => { if (current) setDetail(v) }).catch(() => {})
    load()
    const poll = setInterval(load, 1500)
    return () => { current = false; clearInterval(poll) }
  }, [call, detail?.ended])

  async function start(voice) {
    setBusy(true); setError(''); setDetail(null); setSources([]); setMuted(false); setAppointment(null)
    // Immediately inject greeting so user sees it right away (before first poll)
    const instant_greeting = { role: 'assistant', content: GREETING, language: 'en', interrupted: false }
    setDetail({ messages: [instant_greeting] })
    let next
    try {
      next = await api('/calls', { voice })
      setCall(next); active.current = true
      if (voice) {
        const connection = new Room()
        room.current = connection
        connection.on(RoomEvent.TrackSubscribed, track => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach()
            el.autoplay = true
            el.playsInline = true
            audio.current?.append(el)
            el.play?.().catch(() => {})
          }
        })
        connection.on(RoomEvent.TrackUnsubscribed, track => track.detach().forEach(n => n.remove()))
        connection.on(RoomEvent.Disconnected, () => {
          if (active.current) { active.current = false; setStatus('Disconnected') }
        })
        await connection.connect(next.url, next.token)
        await connection.startAudio()
        await connection.localParticipant.setMicrophoneEnabled(true)
      }
      setStatus(voice ? 'Voice connected – speak now' : 'Text demo active')
    } catch (e) {
      active.current = false
      await room.current?.disconnect()
      room.current = null
      if (next) await api('/calls/' + next.id + '/end', {}).catch(() => {})
      setStatus('Ready'); setError(e.message); setDetail(null)
    } finally { setBusy(false) }
  }

  async function send(value) {
    if (!active.current || !value.trim() || busy) return
    setBusy(true); setTyping(true); setError('')
    try {
      const result = await api('/calls/' + call.id + '/messages', { text: value })
      setSources(result.sources || [])
      if (result.appointment) setAppointment(result.appointment)
      setText('')
      setDetail(await api('/calls/' + call.id))
    } catch (e) { setError(e.message) }
    finally { setBusy(false); setTyping(false) }
  }

  async function end() {
    setBusy(true); setError('')
    try {
      await api('/calls/' + call.id + '/end', {})
      active.current = false
      await room.current?.disconnect()
      room.current = null
      setStatus('Call ended · Generating summary…')
      for (let i = 0; i < 8; i++) {
        await new Promise(r => setTimeout(r, 800))
        const updated = await api('/calls/' + call.id).catch(() => null)
        if (updated) {
          setDetail(updated)
          if (updated.analysis) {
            setStatus('Call ended')
            break
          }
        }
      }
      setStatus('Call ended')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  async function toggleMicrophone() {
    try {
      await room.current.localParticipant.setMicrophoneEnabled(muted)
      setMuted(!muted)
    } catch (e) { setError(e.message) }
  }

  const messages = detail?.messages || []
  const isActive = active.current

  return (
    <>
      <header className="page-heading">
        <div><h1>Call console</h1><p>Talk to the FlowCRM AI sales agent in English or Hindi.</p></div>
      </header>
      <div className="call-layout">
        {/* ── left panel ── */}
        <section className="card control">
          <div className={`orb ${isActive ? (live && call?.mode === 'live' ? 'orb-live' : 'orb-active') : ''}`} aria-hidden="true">
            {[18, 32, 48, 64, 38, 52, 26].map((h, i) => <b key={i} style={{ height: h }} />)}
          </div>
          <h2>AI sales representative</h2>
          <div className="status"><i style={{ background: isActive ? '#29a279' : '#a0a7b8' }} /> {status}</div>

          <div className="controls">
            {!isActive ? (
              <>
                {live && <button className="primary" disabled={busy} onClick={() => start(true)}>🎙 Start voice call</button>}
                <button className={live ? 'secondary' : 'primary'} disabled={busy} onClick={() => start(false)}>💬 Start text chat</button>
              </>
            ) : (
              <>
                {call?.mode === 'live' && (
                  <button className="secondary" onClick={toggleMicrophone}>
                    {muted ? '🔇 Unmute' : '🎙 Mute'}
                  </button>
                )}
                <button className="danger" disabled={busy} onClick={end}>End call</button>
              </>
            )}
          </div>

          {call?.mode === 'demo' && <p className="hint">{live ? 'Text chat · Powered by AI, RAG, & booking.' : 'Text demo · Rule-based responses.'}</p>}

          {/* lead qualification card */}
          {detail?.lead && (
            <div className="lead">
              <span>Lead qualification</span>
              <strong>{detail.lead.score}/100 · {detail.lead.status}</strong>
              {Object.keys(detail.lead.details || {}).length > 0 && (
                <dl>{Object.entries(detail.lead.details).filter(([k]) => !['notes'].includes(k)).map(([k, v]) => (
                  <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
                ))}</dl>
              )}
            </div>
          )}

          {/* appointment confirmation */}
          {appointment && (
            <div className="lead appt-confirmed">
              <span>📅 Demo booked</span>
              <strong>{appointment.date} at {appointment.time}</strong>
              <p>Ref #{appointment.id} – our team will send a calendar invite.</p>
            </div>
          )}
          {/* appointments from DB (after poll) */}
          {!appointment && detail?.appointments?.length > 0 && (
            <div className="lead appt-confirmed">
              <span>📅 Appointment</span>
              {detail.appointments.map(a => (
                <div key={a.id}><strong>{a.date} at {a.time}</strong><p>{a.status}</p></div>
              ))}
            </div>
          )}

          {/* call summary */}
          {detail?.analysis && (
            <div className="lead">
              <span>Call summary · {detail.analysis.sentiment}</span>
              <p>{detail.analysis.summary}</p>
              {detail.analysis.next_action && <p className="hint">→ {detail.analysis.next_action}</p>}
            </div>
          )}

          {error && <p className="error" role="alert">{error}</p>}
          <div ref={audio} />
        </section>

        {/* ── right panel: transcript ── */}
        <section className="card transcript">
          <div className="section-title">
            <h2>Transcript</h2>
            {call?.mode && <span className="badge">{call.mode === 'live' ? 'LIVE VOICE' : 'TEXT DEMO'}</span>}
          </div>

          <Transcript messages={messages} typing={typing} />

          {!!sources.length && <p className="hint">Sources · {sources.join(', ')}</p>}

          {isActive && (
            <>
              <div className="suggestions">
                {suggestions.map(([label, value]) => (
                  <button key={label} disabled={busy} onClick={() => send(value)}>{label}</button>
                ))}
              </div>
              <form className="composer" onSubmit={e => { e.preventDefault(); send(text) }}>
                <input
                  aria-label="Customer message"
                  placeholder={call?.mode === 'live' ? "Type a message (e.g. email, name, or question)…" : "Type a customer message…"}
                  maxLength={1500}
                  value={text}
                  onChange={e => setText(e.target.value)}
                />
                <button className="primary" disabled={!text.trim() || busy}>Send</button>
              </form>
            </>
          )}
        </section>
      </div>
    </>
  )
}

import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import VoiceCall from './pages/VoiceCall.jsx'
import Dashboard from './pages/Dashboard.jsx'
import CallHistory from './pages/CallHistory.jsx'
import './style.css'

const PAGES = [
  { name: 'Call console',  icon: '◉' },
  { name: 'Dashboard',     icon: '▥' },
  { name: 'Call history',  icon: '◷' },
]

function Workspace() {
  const [page, setPage] = useState('Call console')

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">∿</span>
          <div>FlowCRM<small>VOICE WORKSPACE</small></div>
        </div>
        <nav aria-label="Workspace">
          {PAGES.map(({ name, icon }) => (
            <button key={name}
              className={page === name ? 'selected' : ''}
              aria-current={page === name ? 'page' : undefined}
              onClick={() => setPage(name)}>
              <span aria-hidden="true">{icon}</span>{name}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <div hidden={page !== 'Call console'}><VoiceCall /></div>
        {page === 'Dashboard'    && <Dashboard />}
        {page === 'Call history' && <CallHistory />}
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<Workspace />)

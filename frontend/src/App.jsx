import { useState } from 'react'
import Overview from './components/Overview'
import LiveDetection from './components/LiveDetection'
import AlertsTable from './components/AlertsTable'
import ModelsPanel from './components/ModelsPanel'

const TABS = ['Overview', 'Live Detection', 'Alerts', 'Models']

export default function App() {
  const [tab, setTab] = useState('Overview')

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f1117', color: '#e2e8f0' }}>
      <header style={{ backgroundColor: '#1a1d27', borderBottom: '1px solid #2a2d3a', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 12 }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            backgroundColor: '#3b82f6', flexShrink: 0,
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.01em' }}>
            NIDS
          </span>
          <span style={{ color: '#2a2d3a', margin: '0 2px' }}>|</span>
          <span style={{ fontSize: 13, color: '#64748b' }}>
            Network Intrusion Detection System
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.1em',
              color: '#3b82f6', border: '1px solid #1e3a5f',
              padding: '2px 7px', borderRadius: 3, textTransform: 'uppercase',
            }}>
              LIVE
            </span>
            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
              CICIDS2017 · Ensemble: IF + LOF + OC-SVM
            </span>
          </div>
        </div>

        <nav style={{ display: 'flex', marginTop: 10 }}>
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: tab === t ? 500 : 400,
                color: tab === t ? '#e2e8f0' : '#64748b',
                background: 'none',
                border: 'none',
                borderBottom: `2px solid ${tab === t ? '#3b82f6' : 'transparent'}`,
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
                outline: 'none',
              }}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1440, margin: '0 auto' }}>
        {tab === 'Overview'       && <Overview />}
        {tab === 'Live Detection' && <LiveDetection />}
        {tab === 'Alerts'         && <AlertsTable />}
        {tab === 'Models'         && <ModelsPanel />}
      </main>
    </div>
  )
}

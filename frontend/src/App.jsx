import { useState, useEffect } from 'react'
import axios from 'axios'
import Overview from './components/Overview'
import LiveDetection from './components/LiveDetection'
import LiveCapturePanel from './components/LiveCapturePanel'
import AlertsTable from './components/AlertsTable'
import ModelsPanel from './components/ModelsPanel'
import AttackMap from './components/AttackMap'
import LoginPage from './components/LoginPage'

const API  = `${import.meta.env.VITE_API_URL}/api`
const TABS = ['Overview', 'Live Detection', 'Packet Capture', 'Alerts', 'Attack Map', 'Models']

export default function App() {
  const [tab,      setTab]      = useState('Overview')
  const [user,     setUser]     = useState(null)   // null = not checked yet
  const [ready,    setReady]    = useState(false)  // finished verifying token

  useEffect(() => {
    // Handle redirect from Google OAuth: ?token=...&username=...
    const params = new URLSearchParams(window.location.search)
    const oauthToken = params.get('token')
    const oauthUser  = params.get('username')
    const oauthError = params.get('error')

    if (oauthToken && oauthUser) {
      localStorage.setItem('nids_token', oauthToken)
      localStorage.setItem('nids_user',  oauthUser)
      window.history.replaceState({}, '', window.location.pathname)
      setUser(oauthUser)
      setReady(true)
      return
    }

    if (oauthError) {
      window.history.replaceState({}, '', window.location.pathname)
    }

    const token = localStorage.getItem('nids_token')
    if (!token) { setReady(true); return }

    axios.get(`${API}/auth/verify`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (r.data.status === 'ok') setUser(r.data.data.username) })
      .catch(() => { localStorage.removeItem('nids_token'); localStorage.removeItem('nids_user') })
      .finally(() => setReady(true))
  }, [])

  const handleLogin  = (username) => setUser(username)
  const handleLogout = () => {
    localStorage.removeItem('nids_token')
    localStorage.removeItem('nids_user')
    setUser(null)
  }

  if (!ready) return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f1117', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontSize: 12, color: '#64748b' }}>Loading...</span>
    </div>
  )

  if (!user) return <LoginPage onLogin={handleLogin} />

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f1117', color: '#e2e8f0' }}>
      <header style={{ backgroundColor: '#1a1d27', borderBottom: '1px solid #2a2d3a', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 12 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#3b82f6', flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.01em' }}>NIDS</span>
          <span style={{ color: '#2a2d3a', margin: '0 2px' }}>|</span>
          <span style={{ fontSize: 13, color: '#64748b' }}>Network Intrusion Detection System</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', color: '#3b82f6', border: '1px solid #1e3a5f', padding: '2px 7px', borderRadius: 3, textTransform: 'uppercase' }}>LIVE</span>
            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>CICIDS2017 · Ensemble: IF + LOF + OC-SVM + RF</span>
            <span style={{ fontSize: 11, color: '#64748b' }}>|</span>
            <span style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace' }}>{user}</span>
            <button onClick={handleLogout} style={{ fontSize: 11, padding: '3px 10px', borderRadius: 3, backgroundColor: 'transparent', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>
              Logout
            </button>
          </div>
        </div>

        <nav style={{ display: 'flex', marginTop: 10 }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '8px 16px', fontSize: 13,
              fontWeight: tab === t ? 500 : 400,
              color: tab === t ? '#e2e8f0' : '#64748b',
              background: 'none', border: 'none',
              borderBottom: `2px solid ${tab === t ? '#3b82f6' : 'transparent'}`,
              cursor: 'pointer', outline: 'none',
            }}>{t}</button>
          ))}
        </nav>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1440, margin: '0 auto' }}>
        {tab === 'Overview'        && <Overview />}
        {tab === 'Live Detection'  && <LiveDetection />}
        {tab === 'Packet Capture'  && <LiveCapturePanel />}
        {tab === 'Alerts'          && <AlertsTable />}
        {tab === 'Attack Map'      && <AttackMap />}
        {tab === 'Models'          && <ModelsPanel />}
      </main>
    </div>
  )
}

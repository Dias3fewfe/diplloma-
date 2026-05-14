import { useEffect, useRef, useState } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`
const WS_URL = import.meta.env.VITE_API_URL
  ?.replace('https://', 'wss://')
  ?.replace('http://', 'ws://')

const card  = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4 }
const lbl   = { fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b' }
const TH    = { padding: '8px 12px', fontSize: 11, fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#64748b', textAlign: 'left', borderBottom: '1px solid #2a2d3a', background: '#1a1d27' }

const MAX_ROWS = 200

function Badge({ label, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
      color, border: `1px solid ${color}33`, padding: '2px 6px', borderRadius: 3 }}>
      {label}
    </span>
  )
}

export default function LiveCapturePanel() {
  const [interfaces, setInterfaces]   = useState([])
  const [iface, setIface]             = useState('')
  const [running, setRunning]         = useState(false)
  const [flows, setFlows]             = useState([])
  const [stats, setStats]             = useState({ packets_seen: 0, flows_finalized: 0, intrusions: 0 })
  const [error, setError]             = useState(null)
  const [wsState, setWsState]         = useState('closed')  // connecting | open | closed | error
  const wsRef = useRef(null)

  // Load interfaces on mount
  useEffect(() => {
    axios.get(`${API}/capture/interfaces`)
      .then(r => {
        if (r.data.status === 'ok') setInterfaces(r.data.data.interfaces || [])
      })
      .catch(() => setInterfaces([]))
  }, [])

  // Poll status every 3 s while running
  useEffect(() => {
    if (!running) return
    const id = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/capture/status`)
        if (data.status === 'ok') setStats(data.data.stats || {})
      } catch {}
    }, 3000)
    return () => clearInterval(id)
  }, [running])

  const connectWs = () => {
    if (wsRef.current) wsRef.current.close()
    setWsState('connecting')
    const ws = new WebSocket(`${WS_URL}/api/ws/live`)
    wsRef.current = ws

    ws.onopen  = () => setWsState('open')
    ws.onclose = () => setWsState('closed')
    ws.onerror = () => setWsState('error')

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'ping') return
        setFlows(prev => [msg, ...prev].slice(0, MAX_ROWS))
      } catch {}
    }
  }

  const handleStart = async () => {
    setError(null)
    try {
      const { data } = await axios.post(`${API}/capture/start`, { interface: iface || null })
      if (data.status === 'ok') {
        setRunning(true)
        connectWs()
      } else {
        setError(data.error ?? 'Start failed')
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Cannot reach backend')
    }
  }

  const handleStop = async () => {
    try {
      await axios.post(`${API}/capture/stop`)
    } catch {}
    setRunning(false)
    setWsState('closed')
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
  }

  const wsColor = { open: '#10b981', connecting: '#f59e0b', closed: '#64748b', error: '#ef4444' }[wsState]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Controls */}
      <div style={{ ...card, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <select
          value={iface}
          onChange={e => setIface(e.target.value)}
          disabled={running}
          style={{ padding: '6px 10px', fontSize: 12, backgroundColor: '#0f1117', color: '#e2e8f0',
            border: '1px solid #2a2d3a', borderRadius: 4, minWidth: 200 }}
        >
          <option value=''>-- default interface --</option>
          {interfaces.map(i => <option key={i} value={i}>{i}</option>)}
        </select>

        {!running
          ? <button onClick={handleStart} style={{ padding: '7px 18px', fontSize: 13, fontWeight: 500,
              backgroundColor: '#1e3a5f', color: '#3b82f6', border: '1px solid #2a2d3a',
              borderRadius: 4, cursor: 'pointer' }}>
              Start Capture
            </button>
          : <button onClick={handleStop} style={{ padding: '7px 18px', fontSize: 13, fontWeight: 500,
              backgroundColor: '#3b0d0d', color: '#ef4444', border: '1px solid #7f1d1d',
              borderRadius: 4, cursor: 'pointer' }}>
              Stop
            </button>
        }

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: wsColor, display: 'inline-block' }} />
          <span style={{ fontSize: 11, color: wsColor }}>WebSocket {wsState}</span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ ...card, border: '1px solid #7f1d1d', padding: '10px 14px', fontSize: 13, color: '#fca5a5',
          whiteSpace: 'pre-wrap' }}>
          {error}
          {error.includes('Npcap') || error.includes('scapy') ? (
            <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
              Install guide: <code style={{ color: '#f59e0b' }}>pip install scapy</code> then download{' '}
              <strong>Npcap</strong> from npcap.com and restart the backend as Administrator.
            </div>
          ) : null}
        </div>
      )}

      {/* Stats bar */}
      {(running || flows.length > 0) && (
        <div style={{ display: 'flex', gap: 20, fontSize: 13 }}>
          <span style={lbl}>Packets: <span style={{ color: '#94a3b8' }}>{stats.packets_seen ?? 0}</span></span>
          <span style={lbl}>Flows: <span style={{ color: '#94a3b8' }}>{stats.flows_finalized ?? 0}</span></span>
          <span style={lbl}>Intrusions: <span style={{ color: '#ef4444' }}>{stats.intrusions ?? 0}</span></span>
          {flows.length > 0 && <span style={lbl}>Shown: <span style={{ color: '#94a3b8' }}>{flows.length}</span></span>}
        </div>
      )}

      {/* Flow table */}
      {flows.length > 0 && (
        <div style={card}>
          <div style={{ overflowY: 'auto', maxHeight: '60vh' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Src IP', 'Dst IP', 'Port', 'Proto', 'Pkts', 'Bytes', 'Prediction', 'Conf', 'IF', 'LOF', 'SVM'].map((h, i) => (
                    <th key={h} style={{ ...TH, textAlign: i >= 6 ? 'center' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {flows.map((f, i) => {
                  const intr = f.prediction === 'INTRUSION'
                  return (
                    <tr key={i} style={{ backgroundColor: intr ? 'rgba(239,68,68,0.05)' : 'transparent',
                      borderBottom: '1px solid #1e2130' }}>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#94a3b8' }}>{f.src_ip}</td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#94a3b8' }}>{f.dst_ip}</td>
                      <td style={{ padding: '6px 12px', fontFamily: 'monospace', color: '#64748b' }}>{f.dst_port}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b' }}>{f.protocol}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b', textAlign: 'right' }}>{f.packets}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b', textAlign: 'right' }}>{f.bytes}</td>
                      <td style={{ padding: '6px 12px', textAlign: 'center' }}>
                        <Badge label={f.prediction} color={intr ? '#ef4444' : '#10b981'} />
                      </td>
                      <td style={{ padding: '6px 12px', textAlign: 'center', fontFamily: 'monospace', color: '#94a3b8' }}>
                        {((f.attack_confidence ?? 0) * 100).toFixed(0)}%
                      </td>
                      <td style={{ padding: '6px 12px', textAlign: 'center', color: f.model_votes?.isolation_forest ? '#ef4444' : '#2a2d3a' }}>■</td>
                      <td style={{ padding: '6px 12px', textAlign: 'center', color: f.model_votes?.lof ? '#ef4444' : '#2a2d3a' }}>■</td>
                      <td style={{ padding: '6px 12px', textAlign: 'center', color: f.model_votes?.svm ? '#ef4444' : '#2a2d3a' }}>■</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!running && flows.length === 0 && !error && (
        <div style={{ color: '#64748b', fontSize: 13, padding: '20px 0' }}>
          Select a network interface and click <strong style={{ color: '#3b82f6' }}>Start Capture</strong> to begin real-time packet analysis.
          Requires Npcap (Windows) and Administrator privileges.
        </div>
      )}
    </div>
  )
}

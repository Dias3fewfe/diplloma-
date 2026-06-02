import { useState, useRef } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

const card = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4 }
const TH   = { padding: '8px 12px', fontSize: 11, fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#64748b', textAlign: 'left', borderBottom: '1px solid #2a2d3a', background: '#1a1d27' }

const SCENARIOS = [
  { key: 'PortScan',      label: 'Port Scan',     color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.25)', desc: 'Systematic sweep of open ports' },
  { key: 'DDoS',          label: 'DDoS',          color: '#ef4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.25)',  desc: 'Distributed denial-of-service flood' },
  { key: 'DoS Hulk',      label: 'DoS Hulk',      color: '#f97316', bg: 'rgba(249,115,22,0.08)', border: 'rgba(249,115,22,0.25)', desc: 'HTTP GET flood via randomised URLs' },
  { key: 'Bot',           label: 'Botnet',        color: '#a855f7', bg: 'rgba(168,85,247,0.08)', border: 'rgba(168,85,247,0.25)', desc: 'Command-and-control bot traffic' },
  { key: 'DoS GoldenEye', label: 'DoS GoldenEye', color: '#06b6d4', bg: 'rgba(6,182,212,0.08)',  border: 'rgba(6,182,212,0.25)',  desc: 'HTTP keepalive DoS attack' },
]

function Dot({ on, color }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
      backgroundColor: on ? (color || '#ef4444') : '#2a2d3a',
      boxShadow: on ? `0 0 5px ${color || '#ef4444'}` : 'none',
    }} />
  )
}

function AttackRow({ row, index, scenario, visible }) {
  if (!visible) return null
  const intr  = row.prediction === 'INTRUSION'
  const s     = SCENARIOS.find(s => s.key === scenario) || {}
  const votes = Object.values(row.model_votes).reduce((a, b) => a + b, 0)
  const total = Object.keys(row.model_votes).length

  return (
    <tr style={{
      backgroundColor: intr ? `${s.bg || 'rgba(239,68,68,0.05)'}` : 'transparent',
      borderBottom: '1px solid #1e2130',
      animation: 'fadeIn 0.25s ease-out',
    }}>
      <td style={{ padding: '7px 12px', color: '#475569', fontFamily: 'monospace', fontSize: 11 }}>{index + 1}</td>
      <td style={{ padding: '7px 12px' }}>
        <span style={{
          fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', padding: '2px 7px',
          borderRadius: 3, color: s.color || '#ef4444',
          backgroundColor: s.bg || 'rgba(239,68,68,0.08)',
          border: `1px solid ${s.border || 'rgba(239,68,68,0.2)'}`,
        }}>{row.label}</span>
      </td>
      <td style={{ padding: '7px 12px' }}>
        <span style={{
          fontSize: 11, fontWeight: 600, color: intr ? '#ef4444' : '#10b981',
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          {intr ? '⚠ INTRUSION' : '✓ NORMAL'}
        </span>
      </td>
      <td style={{ padding: '7px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 56, height: 4, backgroundColor: '#2a2d3a', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${row.attack_confidence * 100}%`, backgroundColor: intr ? (s.color || '#ef4444') : '#10b981', transition: 'width 0.4s' }} />
          </div>
          <span style={{ color: '#94a3b8', fontFamily: 'monospace', fontSize: 11, minWidth: 30 }}>{(row.attack_confidence * 100).toFixed(0)}%</span>
        </div>
      </td>
      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.isolation_forest} color={s.color} /></td>
      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.lof}              color={s.color} /></td>
      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.svm}              color={s.color} /></td>
      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.random_forest}    color={s.color} /></td>
      <td style={{ padding: '7px 12px', textAlign: 'center', color: '#64748b', fontFamily: 'monospace', fontSize: 11 }}>{votes}/{total}</td>
    </tr>
  )
}

export default function LiveDetection() {
  const [loading,       setLoading]       = useState(false)
  const [activeScenario, setActiveScenario] = useState(null)   // scenario key
  const [allRows,       setAllRows]       = useState([])
  const [visibleCount,  setVisibleCount]  = useState(0)
  const [summary,       setSummary]       = useState(null)
  const [error,         setError]         = useState(null)
  const [mode,          setMode]          = useState(null)     // 'scenario' | 'random'
  const timerRef = useRef(null)

  const clearTimers = () => { if (timerRef.current) clearInterval(timerRef.current) }

  const runScenario = async (scenarioKey) => {
    clearTimers()
    setLoading(true); setError(null); setAllRows([]); setVisibleCount(0); setSummary(null)
    setActiveScenario(scenarioKey); setMode('scenario')
    try {
      const { data } = await axios.post(`${API}/simulate/attack/${encodeURIComponent(scenarioKey)}`)
      if (data.status !== 'ok') { setError(data.error ?? 'Server error'); return }
      const rows = data.data.rows || []
      setSummary(data.data)
      setAllRows(rows)
      // stream rows in one by one
      let i = 0
      timerRef.current = setInterval(() => {
        i++
        setVisibleCount(i)
        if (i >= rows.length) clearInterval(timerRef.current)
      }, 120)
    } catch (e) {
      setError(`Cannot reach backend: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const runRandom = async () => {
    clearTimers()
    setLoading(true); setError(null); setAllRows([]); setVisibleCount(0); setSummary(null)
    setActiveScenario(null); setMode('random')
    try {
      const { data } = await axios.post(`${API}/simulate`)
      if (data.status !== 'ok') { setError(data.error ?? 'Server error'); return }
      const rows = data.data.rows || []
      setSummary(data.data)
      setAllRows(rows)
      let i = 0
      timerRef.current = setInterval(() => {
        i++; setVisibleCount(i)
        if (i >= rows.length) clearInterval(timerRef.current)
      }, 60)
    } catch (e) {
      setError(`Cannot reach backend: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const activeS = SCENARIOS.find(s => s.key === activeScenario)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Attack Scenarios ── */}
      <div style={{ ...card, padding: '18px 20px' }}>
        <div style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 14, fontWeight: 600 }}>
          Attack Scenarios — real traffic patterns from CICIDS2017
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {SCENARIOS.map(s => {
            const isActive = activeScenario === s.key && loading
            const wasRun   = activeScenario === s.key && !loading && allRows.length > 0
            return (
              <button
                key={s.key}
                onClick={() => runScenario(s.key)}
                disabled={loading}
                title={s.desc}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
                  padding: '10px 14px', borderRadius: 6, cursor: loading ? 'not-allowed' : 'pointer',
                  backgroundColor: wasRun ? s.bg : (isActive ? s.bg : '#0f1117'),
                  border: `1px solid ${wasRun || isActive ? s.border : '#2a2d3a'}`,
                  transition: 'all 0.2s', minWidth: 130,
                  opacity: loading && !isActive ? 0.5 : 1,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  {isActive && (
                    <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: s.color, animation: 'pulse 1s infinite' }} />
                  )}
                  <span style={{ fontSize: 13, fontWeight: 600, color: s.color }}>{s.label}</span>
                </div>
                <span style={{ fontSize: 10, color: '#475569', textAlign: 'left', lineHeight: 1.4 }}>{s.desc}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Controls row ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button
          onClick={runRandom}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 18px', fontSize: 13, fontWeight: 500,
            backgroundColor: mode === 'random' && !loading ? 'rgba(59,130,246,0.1)' : '#1e3a5f',
            color: loading && mode === 'random' ? '#64748b' : '#3b82f6',
            border: '1px solid #2a2d3a', borderRadius: 4,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading && mode === 'random' && (
            <span style={{ width: 11, height: 11, border: '2px solid #3b82f6', borderTopColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
          )}
          {loading && mode === 'random' ? 'Analysing 100 flows…' : 'Run Random Simulation'}
        </button>

        {summary && !loading && (
          <div style={{ display: 'flex', gap: 20, fontSize: 13, alignItems: 'center' }}>
            <span style={{ color: '#ef4444', fontWeight: 600 }}>
              {summary.intrusions_detected} intrusions
            </span>
            <span style={{ color: '#10b981', fontWeight: 600 }}>
              {summary.normal_count} normal
            </span>
            <span style={{ color: '#64748b' }}>
              {(summary.detection_rate * 100).toFixed(0)}% detection rate
            </span>
            {mode === 'scenario' && (
              <span style={{ fontSize: 11, color: activeS?.color || '#64748b', fontWeight: 500, padding: '2px 8px', border: `1px solid ${activeS?.border || '#2a2d3a'}`, borderRadius: 3, backgroundColor: activeS?.bg }}>
                {summary.attack_type}
              </span>
            )}
          </div>
        )}

        {loading && mode === 'scenario' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: activeS?.color || '#ef4444' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: activeS?.color || '#ef4444', animation: 'pulse 1s infinite', display: 'inline-block' }} />
            Simulating {activeS?.label} attack…
          </div>
        )}
      </div>

      {error && (
        <div style={{ ...card, border: '1px solid #7f1d1d', padding: '10px 14px', fontSize: 13, color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {/* ── Intrusion Alert Banner ── */}
      {summary && !loading && summary.intrusions_detected > 0 && mode === 'scenario' && (
        <div style={{
          padding: '12px 18px', borderRadius: 6,
          backgroundColor: activeS?.bg || 'rgba(239,68,68,0.08)',
          border: `1px solid ${activeS?.border || 'rgba(239,68,68,0.3)'}`,
          display: 'flex', alignItems: 'center', gap: 12,
          animation: 'fadeIn 0.3s ease-out',
        }}>
          <span style={{ fontSize: 18 }}>⚠</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: activeS?.color || '#ef4444', letterSpacing: '0.04em' }}>
              {summary.intrusions_detected} INTRUSION{summary.intrusions_detected > 1 ? 'S' : ''} DETECTED
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
              {summary.attack_type} attack — {(summary.detection_rate * 100).toFixed(0)}% of flows flagged by ensemble
            </div>
          </div>
        </div>
      )}

      {/* ── Results table ── */}
      {allRows.length > 0 && (
        <div style={card}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #2a2d3a', display: 'flex', gap: 20, fontSize: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#64748b', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {visibleCount} / {allRows.length} flows analysed
            </span>
            <div style={{ flex: 1, height: 3, backgroundColor: '#2a2d3a', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${(visibleCount / allRows.length) * 100}%`, backgroundColor: activeS?.color || '#3b82f6', transition: 'width 0.1s' }} />
            </div>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: '55vh' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['#', 'Label', 'Prediction', 'Confidence', 'IF', 'LOF', 'SVM', 'RF', 'Score'].map((h, i) => (
                    <th key={h} style={{ ...TH, textAlign: i >= 4 ? 'center' : 'left', width: i === 0 ? 36 : 'auto' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allRows.map((row, i) => (
                  <AttackRow
                    key={i}
                    row={row}
                    index={i}
                    scenario={activeScenario || ''}
                    visible={i < visibleCount}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin   { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        @keyframes pulse  { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  )
}

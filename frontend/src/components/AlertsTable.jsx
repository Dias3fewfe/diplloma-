import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API      = `${import.meta.env.VITE_API_URL}/api`
const PAGE     = 20
const card     = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4 }
const TH_STYLE = { padding: '8px 12px', fontSize: 11, fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#64748b', textAlign: 'left', borderBottom: '1px solid #2a2d3a', background: '#1a1d27', position: 'sticky', top: 0 }

function PredBadge({ v }) {
  const intr = v === 'INTRUSION'
  return (
    <span style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.04em', color: intr ? '#ef4444' : '#10b981' }}>{v}</span>
  )
}

function VoteChips({ votes }) {
  const map = { isolation_forest: 'IF', lof: 'LOF', svm: 'SVM' }
  return (
    <span style={{ display: 'flex', gap: 4 }}>
      {Object.entries(votes).map(([k, v]) => (
        <span key={k} style={{ fontSize: 10, fontFamily: 'monospace', padding: '1px 5px', borderRadius: 2, backgroundColor: v ? 'rgba(239,68,68,0.15)' : '#1e2130', color: v ? '#fca5a5' : '#64748b', border: `1px solid ${v ? '#7f1d1d' : '#2a2d3a'}` }}>
          {map[k] ?? k}
        </span>
      ))}
    </span>
  )
}

export default function AlertsTable() {
  const [data,    setData]    = useState({ alerts: [], total: 0 })
  const [page,    setPage]    = useState(0)
  const [filter,  setFilter]  = useState('')
  const [loading, setLoading] = useState(false)

  const fetch = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: PAGE, offset: page * PAGE }
      if (filter) params.prediction = filter
      const { data: res } = await axios.get(`${API}/alerts`, { params })
      if (res.status === 'ok') setData(res.data)
    } catch {}
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { fetch() }, [fetch])

  const pages = Math.ceil(data.total / PAGE)
  const fmt   = ts => new Date(ts).toISOString().replace('T', ' ').slice(0, 19)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 12, color: '#64748b' }}>{data.total.toLocaleString()} alerts</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          {[['', 'All'], ['INTRUSION', 'Intrusions'], ['NORMAL', 'Normal']].map(([f, lbl]) => (
            <button key={f} onClick={() => { setFilter(f); setPage(0) }} style={{
              fontSize: 12, padding: '5px 12px', borderRadius: 3,
              backgroundColor: filter === f ? '#1e3a5f' : '#1a1d27',
              color: filter === f ? '#3b82f6' : '#64748b',
              border: `1px solid ${filter === f ? '#2d5fa6' : '#2a2d3a'}`,
              cursor: 'pointer',
            }}>{lbl}</button>
          ))}
          <button onClick={fetch} style={{ fontSize: 12, padding: '5px 10px', borderRadius: 3, backgroundColor: '#1a1d27', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer' }}>Refresh</button>
        </div>
      </div>

      <div style={card}>
        <div style={{ overflowX: 'auto', maxHeight: '64vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>{['Timestamp', 'Source IP', 'Destination IP', 'Proto', 'Prediction', 'Confidence', 'Models Voted'].map(h => (
                <th key={h} style={TH_STYLE}>{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} style={{ padding: '20px 12px', textAlign: 'center', color: '#64748b', fontSize: 12 }}>Loading…</td></tr>}
              {!loading && data.alerts.length === 0 && (
                <tr><td colSpan={7} style={{ padding: '32px 12px', textAlign: 'center', color: '#64748b', fontSize: 12 }}>No alerts — run a simulation first.</td></tr>
              )}
              {!loading && data.alerts.map(a => (
                <tr key={a.id} style={{ borderBottom: '1px solid #1e2130', backgroundColor: a.prediction === 'INTRUSION' ? 'rgba(239,68,68,0.04)' : 'transparent' }}>
                  <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: '#64748b', whiteSpace: 'nowrap' }}>{fmt(a.created_at)}</td>
                  <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: '#94a3b8' }}>{a.source_ip}</td>
                  <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: '#94a3b8' }}>{a.destination_ip}</td>
                  <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: '#64748b', textTransform: 'uppercase', fontSize: 11 }}>{a.protocol}</td>
                  <td style={{ padding: '7px 12px' }}><PredBadge v={a.prediction} /></td>
                  <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: '#64748b' }}>{(a.attack_confidence * 100).toFixed(0)}%</td>
                  <td style={{ padding: '7px 12px' }}><VoteChips votes={a.model_votes} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#64748b' }}>
          <span>Page {page + 1} of {pages}</span>
          <div style={{ display: 'flex', gap: 6 }}>
            {['Prev', 'Next'].map((lbl, di) => (
              <button key={lbl} onClick={() => setPage(p => Math.max(0, Math.min(pages - 1, p + (di === 0 ? -1 : 1))))}
                disabled={di === 0 ? page === 0 : page >= pages - 1}
                style={{ fontSize: 12, padding: '5px 12px', borderRadius: 3, backgroundColor: '#1a1d27', color: '#64748b', border: '1px solid #2a2d3a', cursor: 'pointer', opacity: (di === 0 ? page === 0 : page >= pages - 1) ? 0.4 : 1 }}>
                {lbl}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

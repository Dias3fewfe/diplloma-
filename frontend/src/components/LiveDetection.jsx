import { useState } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

const card = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4 }
const lbl  = { fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b' }
const TH   = { padding: '8px 12px', fontSize: 11, fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#64748b', textAlign: 'left', borderBottom: '1px solid #2a2d3a', background: '#1a1d27' }

function Dot({ on }) {
  return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', backgroundColor: on ? '#ef4444' : '#2a2d3a', flexShrink: 0 }} />
}

export default function LiveDetection() {
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState(null)

  const run = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const { data } = await axios.post(`${API}/simulate`)
      if (data.status === 'ok') setResult(data.data)
      else setError(data.error ?? 'Server error')
    } catch {
      setError('Cannot reach backend — ensure uvicorn is running on port 8000.')
    } finally { setLoading(false) }
  }

  const rows = Array.isArray(result?.rows) ? result.rows : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <button onClick={run} disabled={loading} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 18px', fontSize: 13, fontWeight: 500,
          backgroundColor: loading ? '#1a1d27' : '#1e3a5f',
          color: loading ? '#64748b' : '#3b82f6',
          border: '1px solid #2a2d3a', borderRadius: 4,
          cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.15s',
        }}>
          {loading && <span style={{ width: 12, height: 12, border: '2px solid #3b82f6', borderTopColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />}
          {loading ? 'Analysing 100 flows…' : 'Run Simulation'}
        </button>

        {result && !loading && (
          <div style={{ display: 'flex', gap: 24, fontSize: 13 }}>
            <span style={{ color: '#ef4444', fontWeight: 500 }}>{result.intrusions_detected} intrusions</span>
            <span style={{ color: '#10b981', fontWeight: 500 }}>{result.normal_count} normal</span>
            <span style={{ color: '#64748b' }}>{(result.detection_rate * 100).toFixed(1)}% detection rate</span>
            <span style={{ color: '#64748b', fontSize: 12, fontFamily: 'monospace' }}>
              IF {result.model_agreement?.isolation_forest} · LOF {result.model_agreement?.lof} · SVM {result.model_agreement?.svm}
            </span>
          </div>
        )}
      </div>

      {error && <div style={{ backgroundColor: '#1a1d27', border: '1px solid #7f1d1d', borderRadius: 4, padding: '10px 14px', fontSize: 13, color: '#fca5a5' }}>{error}</div>}

      {rows.length > 0 && (
        <div style={card}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #2a2d3a', display: 'flex', gap: 20, fontSize: 12 }}>
            <span style={lbl}>{rows.length} flows</span>
            <span style={{ color: '#ef4444' }}>{result.intrusions_detected} intrusions</span>
            <span style={{ color: '#10b981' }}>{result.normal_count} normal</span>
          </div>
          <div style={{ overflowY: 'auto', maxHeight: '62vh' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['#', 'Label', 'Prediction', 'Confidence', 'IF', 'LOF', 'SVM', 'Score'].map((h, i) => (
                    <th key={h} style={{ ...TH, textAlign: i >= 4 ? 'center' : 'left', width: i === 0 ? 40 : 'auto' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => {
                  const intr  = row.prediction === 'INTRUSION'
                  const votes = Object.values(row.model_votes).reduce((a, b) => a + b, 0)
                  return (
                    <tr key={i} style={{ backgroundColor: intr ? 'rgba(239,68,68,0.05)' : 'transparent', borderBottom: '1px solid #1e2130' }}>
                      <td style={{ padding: '7px 12px', color: '#64748b', fontFamily: 'monospace' }}>{i + 1}</td>
                      <td style={{ padding: '7px 12px', color: intr ? '#fca5a5' : '#64748b', fontFamily: 'monospace' }}>{row.label}</td>
                      <td style={{ padding: '7px 12px' }}>
                        <span style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.04em', color: intr ? '#ef4444' : '#10b981' }}>
                          {row.prediction}
                        </span>
                      </td>
                      <td style={{ padding: '7px 12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 56, height: 4, backgroundColor: '#2a2d3a', borderRadius: 1, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${row.attack_confidence * 100}%`, backgroundColor: intr ? '#ef4444' : '#10b981' }} />
                          </div>
                          <span style={{ color: '#94a3b8', fontFamily: 'monospace', minWidth: 28 }}>{(row.attack_confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.isolation_forest} /></td>
                      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.lof} /></td>
                      <td style={{ padding: '7px 12px', textAlign: 'center' }}><Dot on={row.model_votes.svm} /></td>
                      <td style={{ padding: '7px 12px', textAlign: 'center', color: '#64748b', fontFamily: 'monospace' }}>{votes}/3</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

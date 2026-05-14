import { useState, useEffect, useRef } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell } from 'recharts'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

const card  = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4, padding: '14px 18px' }
const label = { fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b', display: 'block', marginBottom: 8 }
const TIP   = { contentStyle: { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', color: '#e2e8f0', borderRadius: 4, fontSize: 12 } }

function StatCard({ lbl, value, sub, color }) {
  return (
    <div style={card}>
      <span style={label}>{lbl}</span>
      <div style={{ fontSize: 28, fontWeight: 600, color: color ?? '#e2e8f0', lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#64748b', marginTop: 5 }}>{sub}</div>}
    </div>
  )
}

function ModelBar({ name, value, max }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
      <span style={{ fontSize: 12, color: '#94a3b8', width: 148, flexShrink: 0 }}>{name}</span>
      <div style={{ flex: 1, height: 5, backgroundColor: '#2a2d3a', borderRadius: 1, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, backgroundColor: '#3b82f6', transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontSize: 12, color: '#64748b', width: 38, textAlign: 'right', fontFamily: 'monospace' }}>{value}</span>
    </div>
  )
}

export default function Overview() {
  const [stats, setStats]         = useState(null)
  const [history, setHistory]     = useState([])
  const [tgActive, setTgActive]   = useState(null)
  const n = useRef(0)

  useEffect(() => {
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API}/stats`)
        if (data.status !== 'ok') return
        setStats(data.data)
        n.current += 1
        const rate = +(data.data.detection_rate * 100).toFixed(1)
        setHistory(h => [...h.slice(-29), { t: n.current, v: rate }])
      } catch {}
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    axios.get(`${API}/notification-status`)
      .then(r => { if (r.data.status === 'ok') setTgActive(r.data.data.telegram_configured) })
      .catch(() => {})
  }, [])

  if (!stats) return <p style={{ color: '#64748b', fontSize: 13, marginTop: 20 }}>Connecting to {API}…</p>

  const mv = stats.model_vote_totals
  const maxV = Math.max(...Object.values(mv), 1)
  const top  = Object.entries(mv).sort((a, b) => b[1] - a[1])[0]?.[0]?.replace(/_/g, ' ') ?? '—'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {tgActive != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: tgActive ? '#10b981' : '#64748b' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: tgActive ? '#10b981' : '#64748b', flexShrink: 0 }} />
          {tgActive ? 'Telegram notifications active' : 'Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env'}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <StatCard lbl="Total Intrusions"  value={stats.intrusion_count.toLocaleString()} sub="alerts in database"         color="#ef4444" />
        <StatCard lbl="Detection Rate"    value={`${(stats.detection_rate * 100).toFixed(1)}%`} sub="intrusions / all alerts"   color="#3b82f6" />
        <StatCard lbl="Leading Detector"  value={top}                                     sub="most anomaly votes cast" />
        <StatCard lbl="Ensemble Status"   value="4 / 4"                                   sub="models operational"            color="#10b981" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={card}>
          <span style={label}>Anomaly votes by model</span>
          <div style={{ marginTop: 14 }}>
            <ModelBar name="Isolation Forest"    value={mv.isolation_forest ?? 0} max={maxV} />
            <ModelBar name="Local Outlier Factor" value={mv.lof ?? 0}              max={maxV} />
            <ModelBar name="One-Class SVM"        value={mv.svm ?? 0}              max={maxV} />
            {mv.random_forest != null && <ModelBar name="Random Forest" value={mv.random_forest} max={maxV} />}
          </div>
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #2a2d3a', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {Object.entries(mv).map(([k, v]) => (
              <div key={k}>
                <span style={{ ...label, marginBottom: 2 }}>{k.replace(/_/g,' ').toUpperCase()}</span>
                <span style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0' }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={card}>
          <span style={label}>Detection rate over time (%)</span>
          {history.length < 2
            ? <p style={{ color: '#64748b', fontSize: 12, textAlign: 'center', marginTop: 44 }}>Collecting — polling every 5 s</p>
            : <ResponsiveContainer width="100%" height={176}>
                <AreaChart data={history} margin={{ top: 6, right: 4, bottom: 0, left: -20 }}>
                  <defs>
                    <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%"   stopColor="#3b82f6" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#2a2d3a" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="t" stroke="#2a2d3a" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} stroke="#2a2d3a" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} unit="%" width={34} />
                  <Tooltip {...TIP} formatter={v => [`${v}%`, 'Detection Rate']} />
                  <Area type="monotone" dataKey="v" stroke="#3b82f6" strokeWidth={1.5} fill="url(#ag)" dot={false} activeDot={{ r: 3, fill: '#3b82f6' }} />
                </AreaChart>
              </ResponsiveContainer>
          }
        </div>
      </div>

      {stats.attack_type_breakdown && Object.keys(stats.attack_type_breakdown).length > 0 && (() => {
        const chartData = Object.entries(stats.attack_type_breakdown)
          .sort(([, a], [, b]) => b - a).slice(0, 5)
          .map(([name, count]) => ({ name, count }))
        const COLORS = ['#ef4444', '#f97316', '#eab308', '#a855f7', '#3b82f6']
        return (
          <div style={card}>
            <span style={label}>Top attack types detected</span>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 96 }}>
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={96} />
                <Tooltip {...TIP} formatter={v => [v, 'alerts']} />
                <Bar dataKey="count" radius={2} maxBarSize={14}>
                  {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )
      })()}
    </div>
  )
}

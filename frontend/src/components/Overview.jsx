import { useState, useEffect } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell, LineChart, Line, Legend } from 'recharts'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

const card  = { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4, padding: '14px 18px' }
const label = { fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b', display: 'block', marginBottom: 8 }
const TIP   = { contentStyle: { backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', color: '#e2e8f0', borderRadius: 4, fontSize: 12 } }

const THREAT_CONFIG = {
  LOW:      { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: '#065f46', label: 'LOW',      sub: 'No intrusions in last hour' },
  MEDIUM:   { color: '#eab308', bg: 'rgba(234,179,8,0.1)',   border: '#713f12', label: 'MEDIUM',   sub: 'Low intrusion activity' },
  HIGH:     { color: '#f97316', bg: 'rgba(249,115,22,0.1)',  border: '#7c2d12', label: 'HIGH',     sub: 'Elevated intrusion activity' },
  CRITICAL: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  border: '#7f1d1d', label: 'CRITICAL', sub: 'Active attack in progress' },
}

function StatCard({ lbl, value, sub, color }) {
  return (
    <div style={card}>
      <span style={label}>{lbl}</span>
      <div style={{ fontSize: 28, fontWeight: 600, color: color ?? '#e2e8f0', lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#64748b', marginTop: 5 }}>{sub}</div>}
    </div>
  )
}

function ThreatCard({ level, recentCount }) {
  const cfg = THREAT_CONFIG[level] ?? THREAT_CONFIG.LOW
  return (
    <div style={{ ...card, backgroundColor: cfg.bg, borderColor: cfg.border, display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ flex: 1 }}>
        <span style={label}>Threat Level</span>
        <div style={{ fontSize: 26, fontWeight: 700, color: cfg.color, letterSpacing: '0.04em', lineHeight: 1.1 }}>{cfg.label}</div>
        <div style={{ fontSize: 12, color: cfg.color, opacity: 0.8, marginTop: 5 }}>{cfg.sub}</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 32, fontWeight: 700, color: cfg.color, fontFamily: 'monospace', lineHeight: 1 }}>{recentCount}</div>
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.05em' }}>last 60 min</div>
      </div>
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
  const [stats,    setStats]    = useState(null)
  const [timeline, setTimeline] = useState([])
  const [tgActive, setTgActive] = useState(null)

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [sRes, tRes] = await Promise.all([
          axios.get(`${API}/stats`),
          axios.get(`${API}/stats/timeline?hours=24`),
        ])
        if (sRes.data.status === 'ok') setStats(sRes.data.data)
        if (tRes.data.status === 'ok') setTimeline(tRes.data.data)
      } catch {}
    }
    fetchAll()
    const id = setInterval(fetchAll, 10000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    axios.get(`${API}/notification-status`)
      .then(r => { if (r.data.status === 'ok') setTgActive(r.data.data.telegram_configured) })
      .catch(() => {})
  }, [])

  if (!stats) return <p style={{ color: '#64748b', fontSize: 13, marginTop: 20 }}>Connecting to {API}…</p>

  const mv   = stats.model_vote_totals
  const maxV = Math.max(...Object.values(mv), 1)
  const top  = Object.entries(mv).sort((a, b) => b[1] - a[1])[0]?.[0]?.replace(/_/g, ' ') ?? '—'
  const hasTimeline = timeline.some(b => b.intrusions > 0 || b.normal > 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {tgActive != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: tgActive ? '#10b981' : '#64748b' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: tgActive ? '#10b981' : '#64748b', flexShrink: 0 }} />
          {tgActive ? 'Telegram notifications active' : 'Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env'}
        </div>
      )}

      {/* Stat cards + Threat Level */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1.3fr', gap: 12 }}>
        <StatCard lbl="Total Intrusions"  value={stats.intrusion_count.toLocaleString()} sub="alerts in database"         color="#ef4444" />
        <StatCard lbl="Detection Rate"    value={`${(stats.detection_rate * 100).toFixed(1)}%`} sub="intrusions / all alerts"   color="#3b82f6" />
        <StatCard lbl="Leading Detector"  value={top}                                     sub="most anomaly votes cast" />
        <StatCard lbl="Ensemble Status"   value="4 / 4"                                   sub="models operational"            color="#10b981" />
        <ThreatCard level={stats.threat_level ?? 'LOW'} recentCount={stats.recent_intrusions_1h ?? 0} />
      </div>

      {/* Timeline */}
      <div style={card}>
        <span style={label}>Intrusion timeline — last 24 hours</span>
        {!hasTimeline
          ? <p style={{ color: '#64748b', fontSize: 12, textAlign: 'center', marginTop: 32, marginBottom: 32 }}>No data yet — run a simulation or live capture</p>
          : <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={timeline} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="gi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#ef4444" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#10b981" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#2a2d3a" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" stroke="#2a2d3a" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} interval={2} />
                <YAxis stroke="#2a2d3a" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} width={28} />
                <Tooltip {...TIP} formatter={(v, n) => [v, n === 'intrusions' ? 'Intrusions' : 'Normal']} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#64748b', paddingTop: 6 }} />
                <Area type="monotone" dataKey="intrusions" stroke="#ef4444" strokeWidth={1.5} fill="url(#gi)" dot={false} activeDot={{ r: 3 }} />
                <Area type="monotone" dataKey="normal"     stroke="#10b981" strokeWidth={1}   fill="url(#gn)" dot={false} activeDot={{ r: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
        }
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* Model votes */}
        <div style={card}>
          <span style={label}>Anomaly votes by model</span>
          <div style={{ marginTop: 14 }}>
            <ModelBar name="Isolation Forest"     value={mv.isolation_forest ?? 0} max={maxV} />
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

        {/* Attack type breakdown */}
        {stats.attack_type_breakdown && Object.keys(stats.attack_type_breakdown).length > 0
          ? (() => {
              const chartData = Object.entries(stats.attack_type_breakdown)
                .sort(([, a], [, b]) => b - a).slice(0, 6)
                .map(([name, count]) => ({ name, count }))
              const COLORS = ['#ef4444','#f97316','#eab308','#a855f7','#3b82f6','#14b8a6']
              return (
                <div style={card}>
                  <span style={label}>Top attack types detected</span>
                  <ResponsiveContainer width="100%" height={185}>
                    <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 100 }}>
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                      <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} width={100} />
                      <Tooltip {...TIP} formatter={v => [v, 'alerts']} />
                      <Bar dataKey="count" radius={2} maxBarSize={14}>
                        {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )
            })()
          : <div style={card}>
              <span style={label}>Top attack types detected</span>
              <p style={{ color: '#64748b', fontSize: 12, textAlign: 'center', marginTop: 60 }}>No intrusion data yet</p>
            </div>
        }
      </div>
    </div>
  )
}

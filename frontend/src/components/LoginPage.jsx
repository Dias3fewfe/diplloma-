import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`
const GOOGLE_AUTH_URL = `${import.meta.env.VITE_API_URL}/api/auth/google`

const NODE_COUNT = 65
const CONNECTION_DIST = 130
const ATTACK_INTERVAL_MS = [1800, 3200]

function NetworkCanvas() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let rafId
    let nodes = []
    let w = 0, h = 0

    const resize = () => {
      w = canvas.width  = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    for (let i = 0; i < NODE_COUNT; i++) {
      nodes.push({
        x:  Math.random() * w,
        y:  Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35,
        vy: (Math.random() - 0.5) * 0.35,
        r:  Math.random() * 1.8 + 1.2,
        alert: 0,       // frames remaining in alert state
        ripples: [],    // [{r, a}]
        packets: [],    // [{tx, ty, t}] travelling packets toward neighbours
      })
    }

    // travelling packet: a small dot that moves from src → dst
    const spawnPacket = (src, dst) => {
      src.packets.push({ tx: dst.x, ty: dst.y, t: 0 })
    }

    let packetTimer = 0

    const scheduleAttack = () => {
      const lo = ATTACK_INTERVAL_MS[0], hi = ATTACK_INTERVAL_MS[1]
      setTimeout(() => {
        const idx = Math.floor(Math.random() * nodes.length)
        nodes[idx].alert = 140
        nodes[idx].ripples = [{ r: 0, a: 0.9 }, { r: 0, a: 0.6 }]
        scheduleAttack()
      }, lo + Math.random() * (hi - lo))
    }
    scheduleAttack()

    const draw = () => {
      ctx.clearRect(0, 0, w, h)

      // subtle grid lines for depth
      ctx.strokeStyle = 'rgba(255,255,255,0.018)'
      ctx.lineWidth = 1
      const step = 60
      for (let x = 0; x < w; x += step) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
      }
      for (let y = 0; y < h; y += step) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
      }

      // update nodes
      nodes.forEach(n => {
        n.x += n.vx; n.y += n.vy
        if (n.x < 0 || n.x > w) n.vx *= -1
        if (n.y < 0 || n.y > h) n.vy *= -1
        if (n.alert > 0) n.alert--
      })

      // spawn packets occasionally
      packetTimer++
      if (packetTimer % 40 === 0) {
        const src = nodes[Math.floor(Math.random() * nodes.length)]
        // find a neighbour
        const neighbours = nodes.filter(n => {
          const dx = n.x - src.x, dy = n.y - src.y
          const d = Math.hypot(dx, dy)
          return d > 0 && d < CONNECTION_DIST
        })
        if (neighbours.length) {
          const dst = neighbours[Math.floor(Math.random() * neighbours.length)]
          spawnPacket(src, dst)
        }
      }

      // draw edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const dx = a.x - b.x, dy = a.y - b.y
          const dist = Math.hypot(dx, dy)
          if (dist < CONNECTION_DIST) {
            const fade = 1 - dist / CONNECTION_DIST
            const isRed = a.alert > 0 || b.alert > 0
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.strokeStyle = isRed
              ? `rgba(239,68,68,${fade * 0.55})`
              : `rgba(59,130,246,${fade * 0.28})`
            ctx.lineWidth = isRed ? 1 : 0.5
            ctx.stroke()
          }
        }
      }

      // draw ripples
      nodes.forEach(n => {
        n.ripples = n.ripples.filter(rp => rp.a > 0.01)
        n.ripples.forEach(rp => {
          rp.r += 1.4
          rp.a -= 0.011
          ctx.beginPath()
          ctx.arc(n.x, n.y, rp.r, 0, Math.PI * 2)
          ctx.strokeStyle = `rgba(239,68,68,${rp.a})`
          ctx.lineWidth = 1.2
          ctx.stroke()
        })
        // feed more ripple rings while alert is active
        if (n.alert > 0 && n.alert % 22 === 0 && n.ripples.length < 4) {
          n.ripples.push({ r: n.r, a: 0.75 })
        }
      })

      // draw travelling packets
      nodes.forEach(n => {
        n.packets = n.packets.filter(p => p.t < 1)
        n.packets.forEach(p => {
          p.t += 0.022
          const px = n.x + (p.tx - n.x) * p.t
          const py = n.y + (p.ty - n.y) * p.t
          ctx.beginPath()
          ctx.arc(px, py, 2, 0, Math.PI * 2)
          ctx.fillStyle = 'rgba(147,197,253,0.85)'
          ctx.fill()
        })
      })

      // draw nodes
      nodes.forEach(n => {
        const isAlert = n.alert > 0
        const color   = isAlert ? '#ef4444' : '#3b82f6'
        const glow    = isAlert ? 'rgba(239,68,68,0.4)' : 'rgba(59,130,246,0.25)'

        // outer glow
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r * 5)
        grad.addColorStop(0, glow)
        grad.addColorStop(1, 'transparent')
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r * 5, 0, Math.PI * 2)
        ctx.fillStyle = grad
        ctx.fill()

        // core dot
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
      })

      rafId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 0 }}
    />
  )
}

// Animated counter that counts up once on mount
function CountUp({ target, suffix = '' }) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    let start = null
    const duration = 1400
    const step = ts => {
      if (!start) start = ts
      const pct = Math.min((ts - start) / duration, 1)
      setVal(Math.floor(pct * target))
      if (pct < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target])
  return <>{val}{suffix}</>
}

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [focusedField, setFocusedField] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('error') === 'google_not_allowed') {
      setError('Access denied: this Google account is not authorized.')
    } else if (params.get('error')) {
      setError('Google sign-in failed. Please try again.')
    }
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data: res } = await axios.post(`${API}/auth/login`, { username, password })
      if (res.status === 'ok') {
        localStorage.setItem('nids_token', res.data.token)
        localStorage.setItem('nids_user',  res.data.username)
        onLogin(res.data.username)
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = (field) => ({
    width: '100%',
    boxSizing: 'border-box',
    backgroundColor: 'rgba(255,255,255,0.04)',
    border: `1px solid ${focusedField === field ? '#3b82f6' : 'rgba(255,255,255,0.08)'}`,
    borderRadius: 8,
    padding: '11px 14px',
    fontSize: 14,
    color: '#e2e8f0',
    outline: 'none',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    boxShadow: focusedField === field ? '0 0 0 3px rgba(59,130,246,0.15)' : 'none',
  })

  const stats = [
    { label: 'Algorithms', value: 4, suffix: '' },
    { label: 'F1 Score',   value: 86, suffix: '%' },
    { label: 'Accuracy',   value: 90, suffix: '%' },
  ]

  return (
    <div style={{ minHeight: '100vh', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#080b12' }}>
      <NetworkCanvas />

      {/* top-left status badge */}
      <div style={{ position: 'fixed', top: 20, left: 24, zIndex: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#22c55e', boxShadow: '0 0 6px #22c55e', display: 'inline-block' }} />
        <span style={{ fontSize: 11, color: '#475569', letterSpacing: '0.1em', textTransform: 'uppercase' }}>System Online</span>
      </div>

      <div style={{ position: 'relative', zIndex: 1, display: 'flex', width: '100%', maxWidth: 1080, padding: '0 48px', gap: 72, alignItems: 'center' }}>

        {/* ── LEFT: branding ── */}
        <div style={{ flex: 1, color: '#e2e8f0' }}>
          <p style={{ margin: '0 0 18px', fontSize: 11, color: '#3b82f6', letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 600 }}>
            Diploma Project · IITU 2026
          </p>

          <h1 style={{ margin: '0 0 16px', fontSize: 44, fontWeight: 700, lineHeight: 1.1, letterSpacing: '-0.02em' }}>
            Network Intrusion<br />
            <span style={{ color: '#3b82f6' }}>Detection System</span>
          </h1>

          <p style={{ margin: '0 0 40px', fontSize: 14, color: '#64748b', lineHeight: 1.75, maxWidth: 400 }}>
            Real-time anomaly detection powered by an ensemble of machine learning models.
            Identifies threats in network traffic using Isolation Forest, LOF, OC-SVM and Random Forest.
          </p>

          {/* stats */}
          <div style={{ display: 'flex', gap: 36 }}>
            {stats.map(s => (
              <div key={s.label}>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#e2e8f0', fontVariantNumeric: 'tabular-nums' }}>
                  <CountUp target={s.value} suffix={s.suffix} />
                </div>
                <div style={{ fontSize: 11, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>

          {/* model tags */}
          <div style={{ display: 'flex', gap: 8, marginTop: 32, flexWrap: 'wrap' }}>
            {['Isolation Forest', 'LOF', 'OC-SVM', 'Random Forest'].map(m => (
              <span key={m} style={{
                padding: '4px 10px',
                fontSize: 11,
                borderRadius: 4,
                border: '1px solid rgba(59,130,246,0.25)',
                color: '#93c5fd',
                backgroundColor: 'rgba(59,130,246,0.08)',
                letterSpacing: '0.04em',
              }}>
                {m}
              </span>
            ))}
          </div>
        </div>

        {/* ── RIGHT: login form ── */}
        <div style={{
          width: 380,
          flexShrink: 0,
          backgroundColor: 'rgba(8,11,18,0.82)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(59,130,246,0.18)',
          borderRadius: 16,
          padding: '40px 36px',
          boxShadow: '0 0 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04) inset',
        }}>
          {/* form header */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#e2e8f0' }}>Sign in</h2>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: '#475569', lineHeight: 1.5 }}>
              Enter your credentials to access the dashboard
            </p>
          </div>

          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                onFocus={() => setFocusedField('username')}
                onBlur={() => setFocusedField(null)}
                autoFocus
                required
                placeholder="admin"
                style={inputStyle('username')}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                required
                placeholder="••••••••"
                style={inputStyle('password')}
              />
            </div>

            {error && (
              <div style={{ padding: '9px 12px', backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8 }}>
                <p style={{ fontSize: 12, color: '#f87171', margin: 0 }}>{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: 4,
                padding: '12px 0',
                backgroundColor: loading ? '#1d3f7a' : '#2563eb',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.75 : 1,
                transition: 'background-color 0.2s',
                letterSpacing: '0.02em',
              }}
              onMouseEnter={e => { if (!loading) e.target.style.backgroundColor = '#1d4ed8' }}
              onMouseLeave={e => { if (!loading) e.target.style.backgroundColor = '#2563eb' }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '22px 0 18px' }}>
            <div style={{ flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.06)' }} />
            <span style={{ fontSize: 11, color: '#334155' }}>or continue with</span>
            <div style={{ flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,0.06)' }} />
          </div>

          <a
            href={GOOGLE_AUTH_URL}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              padding: '11px 0',
              backgroundColor: 'rgba(255,255,255,0.04)',
              color: '#cbd5e1',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              textDecoration: 'none',
              transition: 'background-color 0.2s, border-color 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)' }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
          >
            <svg width="16" height="16" viewBox="0 0 48 48" fill="none">
              <path d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34.3 6.5 29.4 4 24 4 12.95 4 4 12.95 4 24s8.95 20 20 20 20-8.95 20-20c0-1.2-.1-2.3-.4-3.5z" fill="#FFC107"/>
              <path d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34.3 6.5 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" fill="#FF3D00"/>
              <path d="M24 44c5.2 0 9.9-1.9 13.5-5L31.8 33.5C29.8 35 27 36 24 36c-5.3 0-9.7-3.1-11.3-7.5l-6.6 5.1C9.5 39.5 16.2 44 24 44z" fill="#4CAF50"/>
              <path d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4-4.1 5.3l6.7 5.5C41.6 35.6 44 30.3 44 24c0-1.2-.1-2.3-.4-3.5z" fill="#1976D2"/>
            </svg>
            Sign in with Google
          </a>

          <p style={{ marginTop: 18, fontSize: 11, color: '#2d3f5a', textAlign: 'center' }}>
            Default credentials: admin / admin123
          </p>
        </div>
      </div>
    </div>
  )
}

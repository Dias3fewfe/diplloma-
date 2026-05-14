import { useState } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

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

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f1117', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 360, backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 6, padding: '36px 32px' }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#3b82f6' }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.01em' }}>NIDS</span>
          <span style={{ fontSize: 12, color: '#64748b', marginLeft: 2 }}>/ Login</span>
        </div>

        <p style={{ fontSize: 11, color: '#64748b', marginBottom: 24, lineHeight: 1.5 }}>
          Network Intrusion Detection System<br />
          Enter your credentials to access the dashboard.
        </p>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <label style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
              required
              style={{ backgroundColor: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 3, padding: '8px 10px', fontSize: 13, color: '#e2e8f0', outline: 'none' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <label style={{ fontSize: 11, color: '#64748b', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ backgroundColor: '#0f1117', border: '1px solid #2a2d3a', borderRadius: 3, padding: '8px 10px', fontSize: 13, color: '#e2e8f0', outline: 'none' }}
            />
          </div>

          {error && (
            <p style={{ fontSize: 12, color: '#ef4444', margin: 0 }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ marginTop: 6, padding: '9px 0', backgroundColor: '#1e3a5f', color: '#3b82f6', border: '1px solid #2d5fa6', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p style={{ marginTop: 24, fontSize: 10, color: '#334155', textAlign: 'center' }}>
          Default: admin / admin123
        </p>
      </div>
    </div>
  )
}

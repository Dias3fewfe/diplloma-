import { useState, useEffect } from 'react'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`
const GOOGLE_AUTH_URL = `${import.meta.env.VITE_API_URL}/api/auth/google`

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

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

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '20px 0 16px' }}>
          <div style={{ flex: 1, height: 1, backgroundColor: '#2a2d3a' }} />
          <span style={{ fontSize: 11, color: '#334155' }}>or</span>
          <div style={{ flex: 1, height: 1, backgroundColor: '#2a2d3a' }} />
        </div>

        <a
          href={GOOGLE_AUTH_URL}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '9px 0', backgroundColor: '#1a1d27', color: '#e2e8f0', border: '1px solid #2a2d3a', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', textDecoration: 'none' }}
        >
          <svg width="16" height="16" viewBox="0 0 48 48" fill="none">
            <path d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34.3 6.5 29.4 4 24 4 12.95 4 4 12.95 4 24s8.95 20 20 20 20-8.95 20-20c0-1.2-.1-2.3-.4-3.5z" fill="#FFC107"/>
            <path d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34.3 6.5 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" fill="#FF3D00"/>
            <path d="M24 44c5.2 0 9.9-1.9 13.5-5L31.8 33.5C29.8 35 27 36 24 36c-5.3 0-9.7-3.1-11.3-7.5l-6.6 5.1C9.5 39.5 16.2 44 24 44z" fill="#4CAF50"/>
            <path d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4-4.1 5.3l6.7 5.5C41.6 35.6 44 30.3 44 24c0-1.2-.1-2.3-.4-3.5z" fill="#1976D2"/>
          </svg>
          Sign in with Google
        </a>

        <p style={{ marginTop: 16, fontSize: 10, color: '#334155', textAlign: 'center' }}>
          Default: admin / admin123
        </p>
      </div>
    </div>
  )
}

import { useEffect, useState, useRef } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import axios from 'axios'

const API = `${import.meta.env.VITE_API_URL}/api`

const TYPE_COLOR = {
  DDoS:              '#ef4444',
  'DoS Hulk':        '#ef4444',
  'DoS GoldenEye':   '#f97316',
  'DoS slowloris':   '#f97316',
  'DoS Slowhttptest':'f97316',
  PortScan:          '#eab308',
  Bot:               '#a855f7',
  Infiltration:      '#14b8a6',
  Heartbleed:        '#ec4899',
}
const typeColor = t => TYPE_COLOR[t] || '#ef4444'
const fmt = ts => new Date(ts).toISOString().replace('T', ' ').slice(0, 19)

const PULSE_CSS = `
@keyframes nids-ping {
  0%   { transform: scale(1);   opacity: 0.8; }
  70%  { transform: scale(2.4); opacity: 0;   }
  100% { transform: scale(2.4); opacity: 0;   }
}
.nids-ping { animation: nids-ping 1.8s ease-out infinite; }
`

export default function AttackMap() {
  const [attacks,  setAttacks]  = useState([])   // {ip, lat, lng, country, city, countryCode, attackType, confidence, timestamp}
  const [feed,     setFeed]     = useState([])   // last 12 attacks for sidebar
  const [stats,    setStats]    = useState({ total: 0, ips: 0, countries: 0 })
  const [status,   setStatus]   = useState('Loading…')
  const [demoBusy, setDemoBusy] = useState(false)
  const seenIds = useRef(new Set())

  useEffect(() => {
    const style = document.createElement('style')
    style.textContent = PULSE_CSS
    document.head.appendChild(style)
    return () => document.head.removeChild(style)
  }, [])

  const loadAttacks = async () => {
    try {
      const { data: res } = await axios.get(`${API}/alerts`, {
        params: { prediction: 'INTRUSION', limit: 200, offset: 0 },
        headers: { Authorization: `Bearer ${localStorage.getItem('nids_token')}` },
      })
      if (res.status !== 'ok') return

      const fresh = res.data.alerts.filter(a => !seenIds.current.has(a.id))
      if (!fresh.length) { setStatus('Live'); return }
      fresh.forEach(a => seenIds.current.add(a.id))

      const ips = [...new Set(fresh.map(a => a.source_ip).filter(ip => ip && ip !== 'unknown'))]
      if (!ips.length) { setStatus('Live — no public IPs yet'); return }

      const { data: geoMap } = await axios.post(`${API}/geo/batch`, { ips })

      const newPoints = []
      for (const alert of fresh) {
        const geo = geoMap[alert.source_ip]
        if (!geo) continue
        newPoints.push({
          id: alert.id,
          ip: alert.source_ip,
          lat: null,  // ip-api returns lat/lng, we need to request them
          lng: null,
          country: geo.country,
          city: geo.city,
          countryCode: geo.countryCode,
          attackType: alert.attack_type,
          confidence: alert.attack_confidence,
          timestamp: alert.created_at,
        })
      }

      // fetch lat/lng separately (ip-api batch with lat/lng fields)
      const publicIps = [...new Set(newPoints.map(p => p.ip))]
      if (publicIps.length) {
        try {
          const resp = await fetch(
            `http://ip-api.com/batch?fields=query,status,lat,lon,country,countryCode,city`,
            { method: 'POST', body: JSON.stringify(publicIps.map(q => ({ query: q }))) }
          )
          const rows = await resp.json()
          const latLng = {}
          rows.forEach(r => { if (r.status === 'success') latLng[r.query] = { lat: r.lat, lng: r.lon } })
          newPoints.forEach(p => {
            const ll = latLng[p.ip]
            if (ll) { p.lat = ll.lat; p.lng = ll.lng }
          })
        } catch {}
      }

      const withCoords = newPoints.filter(p => p.lat !== null)

      setAttacks(prev => {
        const next = [...withCoords, ...prev].slice(0, 500)
        const uniqueIps     = new Set(next.map(p => p.ip)).size
        const uniqueCountries = new Set(next.map(p => p.country).filter(Boolean)).size
        setStats({ total: next.length, ips: uniqueIps, countries: uniqueCountries })
        return next
      })
      setFeed(prev => [...withCoords, ...prev].slice(0, 12))
      setStatus('Live')
    } catch {
      setStatus('Error loading data')
    }
  }

  const loadDemo = async () => {
    setDemoBusy(true)
    try {
      await axios.post(`${API}/demo/populate`, {}, {
        headers: { Authorization: `Bearer ${localStorage.getItem('nids_token')}` },
      })
      seenIds.current.clear()   // reset so all demo alerts are picked up
      await loadAttacks()
    } catch {}
    finally { setDemoBusy(false) }
  }

  useEffect(() => {
    loadAttacks()
    const id = setInterval(loadAttacks, 5000)
    return () => clearInterval(id)
  }, [])

  const statBox = (label, value) => (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444', fontFamily: 'monospace' }}>{value}</div>
      <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 'calc(100vh - 130px)' }}>

      {/* Stats bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 32, padding: '10px 16px', backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: status === 'Live' ? '#10b981' : '#f59e0b', display: 'inline-block' }} />
          <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>{status}</span>
        </div>
        <div style={{ width: 1, height: 28, backgroundColor: '#2a2d3a' }} />
        {statBox('Attacks plotted', stats.total)}
        {statBox('Unique IPs', stats.ips)}
        {statBox('Countries', stats.countries)}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 10, color: '#334155' }}>Auto-refresh every 5s · Public IPs only</span>
          <button
            onClick={loadDemo}
            disabled={demoBusy}
            style={{ fontSize: 11, padding: '4px 12px', borderRadius: 3, backgroundColor: demoBusy ? '#1a1d27' : '#1e3a5f', color: demoBusy ? '#334155' : '#3b82f6', border: '1px solid #2d5fa6', cursor: demoBusy ? 'not-allowed' : 'pointer' }}
          >
            {demoBusy ? 'Loading…' : 'Load Demo Data'}
          </button>
        </div>
      </div>

      {/* Map + sidebar */}
      <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 0 }}>

        {/* Map */}
        <div style={{ flex: 1, borderRadius: 4, overflow: 'hidden', border: '1px solid #2a2d3a' }}>
          <MapContainer
            center={[20, 0]} zoom={2} minZoom={2} maxZoom={10}
            style={{ height: '100%', width: '100%', background: '#0f1117' }}
            zoomControl={true}
            attributionControl={false}
          >
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution="&copy; CartoDB"
            />

            {attacks.map(a => (
              <CircleMarker
                key={a.id}
                center={[a.lat, a.lng]}
                radius={7}
                pathOptions={{ color: typeColor(a.attackType), fillColor: typeColor(a.attackType), fillOpacity: 0.85, weight: 1.5 }}
              >
                <Popup>
                  <div style={{ fontFamily: 'monospace', fontSize: 12, lineHeight: 1.7, minWidth: 180 }}>
                    <div style={{ fontWeight: 700, color: typeColor(a.attackType), marginBottom: 4 }}>{a.attackType}</div>
                    <div><span style={{ color: '#888' }}>IP</span>   {a.ip}</div>
                    <div><span style={{ color: '#888' }}>Loc</span>  {a.city ? `${a.city}, ` : ''}{a.country}</div>
                    <div><span style={{ color: '#888' }}>Conf</span> {(a.confidence * 100).toFixed(0)}%</div>
                    <div style={{ color: '#888', fontSize: 11 }}>{fmt(a.timestamp)}</div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}

            {/* Outer pulse ring for the 5 most recent */}
            {attacks.slice(0, 5).map(a => (
              <CircleMarker
                key={`ring-${a.id}`}
                center={[a.lat, a.lng]}
                radius={14}
                pathOptions={{ color: typeColor(a.attackType), fillColor: 'transparent', fillOpacity: 0, weight: 1, opacity: 0.4 }}
                className="nids-ping"
              />
            ))}
          </MapContainer>
        </div>

        {/* Live feed sidebar */}
        <div style={{ width: 260, backgroundColor: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 4, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '10px 12px', borderBottom: '1px solid #2a2d3a', fontSize: 11, fontWeight: 600, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Live Feed
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {feed.length === 0 && (
              <div style={{ padding: '20px 12px', fontSize: 11, color: '#334155', textAlign: 'center' }}>
                No public-IP attacks yet.<br />Run Live Capture to see real traffic.
              </div>
            )}
            {feed.map(a => (
              <div key={a.id} style={{ padding: '8px 12px', borderBottom: '1px solid #1e2130' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: typeColor(a.attackType), fontFamily: 'monospace' }}>{a.attackType}</span>
                  <span style={{ fontSize: 10, color: '#334155', fontFamily: 'monospace' }}>{(a.confidence * 100).toFixed(0)}%</span>
                </div>
                <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>{a.ip}</div>
                <div style={{ fontSize: 10, color: '#475569' }}>{a.city ? `${a.city}, ` : ''}{a.country}</div>
                <div style={{ fontSize: 10, color: '#334155', marginTop: 2 }}>{fmt(a.timestamp)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

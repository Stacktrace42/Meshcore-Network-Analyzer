import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

// Use relative URL so nginx can proxy to processing service
const API_URL = ''

interface SystemStats {
  total_repeaters: number
  total_listeners: number
  active_listeners: number
  total_paths: number
  paths_this_week: number
  total_traces: number
  pending_traces: number
  completed_traces: number
  failed_traces: number
  last_graph_update?: string
}

interface AdminDashboardProps {
  apiKey: string
  onLogout: () => void
}

export default function AdminDashboard({ apiKey, onLogout }: AdminDashboardProps) {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/stats`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      })
      setStats(response.data)
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 10000)
    return () => clearInterval(interval)
  }, [apiKey])

  if (loading) {
    return <div style={{ padding: '2rem' }}>Loading...</div>
  }

  return (
    <div style={{ minHeight: '100vh', background: '#1a1a1a' }}>
      <header style={{
        background: '#2a2a2a',
        padding: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Admin Dashboard</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/map" style={{ color: '#4CAF50', textDecoration: 'none' }}>
            Map
          </Link>
          <Link to="/traces" style={{ color: '#4CAF50', textDecoration: 'none' }}>
            Traces
          </Link>
          <Link to="/config" style={{ color: '#4CAF50', textDecoration: 'none' }}>
            Configuration
          </Link>
          <button onClick={onLogout} style={{
            padding: '0.5rem 1rem',
            background: '#f44336',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}>
            Logout
          </button>
        </div>
      </header>

      <div style={{ padding: '2rem' }}>
        <h2 style={{ marginBottom: '1rem' }}>System Statistics</h2>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '1rem'
        }}>
          <StatCard title="Total Repeaters" value={stats?.total_repeaters || 0} />
          <StatCard title="Active Listeners" value={`${stats?.active_listeners || 0} / ${stats?.total_listeners || 0}`} />
          <StatCard title="Total Paths" value={stats?.total_paths || 0} />
          <StatCard title="Paths This Week" value={stats?.paths_this_week || 0} />
          <StatCard title="Pending Traces" value={stats?.pending_traces || 0} />
          <StatCard title="Completed Traces" value={stats?.completed_traces || 0} />
          <StatCard title="Failed Traces" value={stats?.failed_traces || 0} />
        </div>

        {stats?.last_graph_update && (
          <div style={{ marginTop: '2rem' }}>
            <p>
              Last graph update: {new Date(stats.last_graph_update).toLocaleString()}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ title, value }: { title: string, value: string | number }) {
  return (
    <div style={{
      background: '#2a2a2a',
      padding: '1.5rem',
      borderRadius: '8px',
      border: '1px solid #444'
    }}>
      <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#888' }}>
        {title}
      </h3>
      <p style={{ margin: 0, fontSize: '2rem', fontWeight: 'bold' }}>
        {value}
      </p>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

const API_URL = ''

interface TraceSchedule {
  id: string
  from_repeater_name: string | null
  from_repeater_hash: string
  to_repeater_name: string | null
  to_repeater_hash: string
  assigned_listener_name: string | null
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  scheduled_at: string
  completed_at: string | null
  result: any
  calculated_path?: string[]
  path_strategy?: string
}

interface TracesPageProps {
  apiKey: string
  onLogout: () => void
}

interface SchedulerStatus {
  enabled: boolean
  paused: boolean
  total_scheduled: number
  pending: number
  in_progress: number
  completed: number
  failed: number
}

export default function TracesPage({ apiKey, onLogout }: TracesPageProps) {
  const [traces, setTraces] = useState<TraceSchedule[]>([])
  const [status, setStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [toggling, setToggling] = useState(false)
  const [pageSize, setPageSize] = useState<number>(50)
  const [offset, setOffset] = useState<number>(0)
  const [totalCount, setTotalCount] = useState<number>(0)

  const fetchTraces = async () => {
    try {
      const params: any = {
        limit: pageSize,
        offset: offset
      }
      if (statusFilter) {
        params.status_filter = statusFilter
      }
      const response = await axios.get(`${API_URL}/api/v1/traces`, {
        headers: { 'Authorization': `Bearer ${apiKey}` },
        params
      })
      setTraces(response.data)
      setTotalCount(response.data.length < pageSize ? offset + response.data.length : offset + pageSize + 1)
      setError(null)
    } catch (err) {
      setError('Failed to fetch traces')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/traces/status`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      })
      setStatus(response.data)
    } catch (err) {
      console.error('Failed to fetch scheduler status:', err)
    }
  }

  const togglePause = async () => {
    if (!status) return

    setToggling(true)
    try {
      const endpoint = status.paused ? '/api/v1/admin/traces/resume' : '/api/v1/admin/traces/pause'
      await axios.post(`${API_URL}${endpoint}`, {}, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      })
      // Refresh status
      await fetchStatus()
    } catch (err: any) {
      console.error('Failed to toggle pause:', err)
      if (err.response?.status === 403) {
        alert('Permission denied: This action requires admin access')
      } else {
        alert('Failed to toggle trace scheduling')
      }
    } finally {
      setToggling(false)
    }
  }

  useEffect(() => {
    fetchTraces()
    fetchStatus()
    const interval = setInterval(() => {
      fetchTraces()
      fetchStatus()
    }, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [apiKey, statusFilter, pageSize, offset])

  const handlePreviousPage = () => {
    setOffset(Math.max(0, offset - pageSize))
  }

  const handleNextPage = () => {
    setOffset(offset + pageSize)
  }

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize)
    setOffset(0)
  }

  const formatPath = (path?: string[]): string => {
    if (!path || path.length === 0) return '-'
    return path.join(' → ')
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return '#4CAF50'
      case 'in_progress': return '#2196F3'
      case 'pending': return '#FF9800'
      case 'failed': return '#f44336'
      default: return '#999'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return '✓'
      case 'in_progress': return '⟳'
      case 'pending': return '⏳'
      case 'failed': return '✗'
      default: return '?'
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '2rem', background: '#1a1a1a', minHeight: '100vh', color: '#fff' }}>
        Loading...
      </div>
    )
  }

  return (
    <div style={{ background: '#1a1a1a', minHeight: '100vh', color: '#fff' }}>
      <header style={{
        background: '#2a2a2a',
        padding: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #444'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Trace Management</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/" style={{ color: '#4CAF50', textDecoration: 'none' }}>Map</Link>
          <Link to="/admin" style={{ color: '#4CAF50', textDecoration: 'none' }}>Dashboard</Link>
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
        {error && (
          <div style={{
            padding: '1rem',
            background: '#f44336',
            color: 'white',
            borderRadius: '4px',
            marginBottom: '1rem'
          }}>
            {error}
          </div>
        )}

        {/* Status Cards */}
        {status && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '1rem',
            marginBottom: '2rem'
          }}>
            <div style={{ background: '#2a2a2a', padding: '1rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.9rem', color: '#999' }}>Total Traces</div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold' }}>{status.total_scheduled}</div>
            </div>
            <div style={{ background: '#2a2a2a', padding: '1rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.9rem', color: '#999' }}>Pending</div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#FF9800' }}>{status.pending}</div>
            </div>
            <div style={{ background: '#2a2a2a', padding: '1rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.9rem', color: '#999' }}>In Progress</div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#2196F3' }}>{status.in_progress}</div>
            </div>
            <div style={{ background: '#2a2a2a', padding: '1rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.9rem', color: '#999' }}>Completed</div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#4CAF50' }}>{status.completed}</div>
            </div>
            <div style={{ background: '#2a2a2a', padding: '1rem', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.9rem', color: '#999' }}>Failed</div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#f44336' }}>{status.failed}</div>
            </div>
          </div>
        )}

        {/* Controls */}
        <div style={{
          background: '#2a2a2a',
          padding: '1rem',
          borderRadius: '8px',
          marginBottom: '2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <label style={{ fontSize: '0.9rem' }}>Filter:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '0.5rem',
                background: '#1a1a1a',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <button
            onClick={togglePause}
            disabled={toggling || !status}
            style={{
              padding: '0.75rem 1.5rem',
              background: status?.paused ? '#4CAF50' : '#FF9800',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: toggling ? 'wait' : 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold',
              opacity: toggling ? 0.7 : 1
            }}
          >
            {toggling ? '...' : status?.paused ? '▶ Resume Scheduling' : '⏸ Pause Scheduling'}
          </button>
        </div>

        {/* Traces Table */}
        <div style={{ background: '#2a2a2a', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#333', borderBottom: '2px solid #444' }}>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Status</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>From</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>To</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Calculated Path</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Listener</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Scheduled</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Completed</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Result</th>
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                      No traces found
                    </td>
                  </tr>
                ) : (
                  traces.map((trace) => (
                    <tr key={trace.id} style={{ borderBottom: '1px solid #333' }}>
                      <td style={{ padding: '1rem' }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '12px',
                          background: getStatusColor(trace.status) + '33',
                          color: getStatusColor(trace.status),
                          fontSize: '0.85rem',
                          fontWeight: 'bold'
                        }}>
                          {getStatusIcon(trace.status)} {trace.status}
                        </span>
                      </td>
                      <td style={{ padding: '1rem' }}>
                        <div style={{ fontWeight: 'bold' }}>{trace.from_repeater_name || 'Unnamed'}</div>
                        <div style={{ fontSize: '0.85rem', color: '#999', fontFamily: 'monospace' }}>
                          {trace.from_repeater_hash}
                        </div>
                      </td>
                      <td style={{ padding: '1rem' }}>
                        <div style={{ fontWeight: 'bold' }}>{trace.to_repeater_name || 'Unnamed'}</div>
                        <div style={{ fontSize: '0.85rem', color: '#999', fontFamily: 'monospace' }}>
                          {trace.to_repeater_hash}
                        </div>
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.85rem', fontFamily: 'monospace', color: '#4CAF50' }}>
                        {formatPath(trace.calculated_path)}
                      </td>
                      <td style={{ padding: '1rem', color: '#999' }}>
                        {trace.assigned_listener_name || 'Not assigned'}
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#999' }}>
                        {new Date(trace.scheduled_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#999' }}>
                        {trace.completed_at ? new Date(trace.completed_at).toLocaleString() : '-'}
                      </td>
                      <td style={{ padding: '1rem', fontSize: '0.85rem' }}>
                        {trace.result ? (
                          <details style={{ cursor: 'pointer' }}>
                            <summary style={{ color: '#4CAF50' }}>View</summary>
                            <pre style={{
                              marginTop: '0.5rem',
                              padding: '0.5rem',
                              background: '#1a1a1a',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              overflow: 'auto',
                              maxWidth: '300px'
                            }}>
                              {JSON.stringify(trace.result, null, 2)}
                            </pre>
                          </details>
                        ) : (
                          <span style={{ color: '#666' }}>-</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pagination Controls */}
        <div style={{
          marginTop: '1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '1rem',
          background: '#2a2a2a',
          borderRadius: '8px'
        }}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <span style={{ color: '#666', fontSize: '0.9rem' }}>
              Showing {offset + 1}-{offset + traces.length} of {totalCount >= offset + pageSize ? '>' : ''}{totalCount}
            </span>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <label style={{ color: '#999', fontSize: '0.9rem' }}>Per page:</label>
              <select
                value={pageSize}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                style={{
                  padding: '0.5rem',
                  background: '#1a1a1a',
                  color: '#fff',
                  border: '1px solid #444',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handlePreviousPage}
              disabled={offset === 0}
              style={{
                padding: '0.5rem 1rem',
                background: offset === 0 ? '#333' : '#4CAF50',
                color: offset === 0 ? '#666' : 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: offset === 0 ? 'not-allowed' : 'pointer'
              }}
            >
              ← Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={traces.length < pageSize}
              style={{
                padding: '0.5rem 1rem',
                background: traces.length < pageSize ? '#333' : '#4CAF50',
                color: traces.length < pageSize ? '#666' : 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: traces.length < pageSize ? 'not-allowed' : 'pointer'
              }}
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

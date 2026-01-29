import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface ListenersPageProps {
  apiKey: string
  onLogout: () => void
}

interface Listener {
  id: string
  name: string
  last_seen: string | null
  active: boolean
  created_at: string
}

const API_BASE_URL = ''

export default function ListenersPage({ apiKey, onLogout }: ListenersPageProps) {
  const [listeners, setListeners] = useState<Listener[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false)
  const [showApiKeyModal, setShowApiKeyModal] = useState(false)
  const [newListenerName, setNewListenerName] = useState('')
  const [newApiKey, setNewApiKey] = useState('')
  const [creating, setCreating] = useState(false)

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')

  // Delete state
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchListeners()
    const interval = setInterval(fetchListeners, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchListeners = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/listeners`, {
        headers: {
          'Authorization': `Bearer ${apiKey}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch listeners')
      }

      const data = await response.json()
      setListeners(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateListener = async () => {
    if (!newListenerName.trim()) {
      setMessage('Error: Listener name cannot be empty')
      return
    }

    setCreating(true)
    setMessage(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/listeners`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: newListenerName.trim() })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create listener')
      }

      const result = await response.json()
      setNewApiKey(result.api_key)
      setShowAddModal(false)
      setShowApiKeyModal(true)
      setNewListenerName('')
      await fetchListeners()
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : 'An error occurred'}`)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdateListener = async (id: string, name: string) => {
    if (!name.trim()) {
      setMessage('Error: Listener name cannot be empty')
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/listeners/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: name.trim() })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update listener')
      }

      setMessage('Success: Listener updated')
      setEditingId(null)
      await fetchListeners()
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : 'An error occurred'}`)
    }
  }

  const handleDeleteListener = async (id: string) => {
    setDeleting(true)
    setMessage(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/listeners/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${apiKey}`
        }
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to deactivate listener')
      }

      setMessage('Success: Listener deactivated')
      setDeleteConfirmId(null)
      await fetchListeners()
    } catch (err) {
      setMessage(`Error: ${err instanceof Error ? err.message : 'An error occurred'}`)
    } finally {
      setDeleting(false)
    }
  }

  const copyToClipboard = async () => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(newApiKey)
        setMessage('Success: API key copied to clipboard')
      } else {
        // Fallback method for older browsers or when clipboard API fails
        const textArea = document.createElement('textarea')
        textArea.value = newApiKey
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        textArea.style.top = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        try {
          document.execCommand('copy')
          setMessage('Success: API key copied to clipboard')
        } catch (err) {
          setMessage('Error: Failed to copy to clipboard')
        }
        document.body.removeChild(textArea)
      }
    } catch (err) {
      setMessage(`Error: Failed to copy to clipboard - ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const copyListenerId = async (id: string) => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(id)
        setMessage('Success: Listener ID copied to clipboard')
      } else {
        // Fallback method for older browsers or when clipboard API fails
        const textArea = document.createElement('textarea')
        textArea.value = id
        textArea.style.position = 'fixed'
        textArea.style.left = '-999999px'
        textArea.style.top = '-999999px'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        try {
          document.execCommand('copy')
          setMessage('Success: Listener ID copied to clipboard')
        } catch (err) {
          setMessage('Error: Failed to copy to clipboard')
        }
        document.body.removeChild(textArea)
      }
    } catch (err) {
      setMessage(`Error: Failed to copy to clipboard - ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}min ago`
    if (diffHours < 24) return `${diffHours}hr ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  const truncateId = (id: string) => {
    return id.substring(0, 8) + '...'
  }

  if (loading) {
    return (
      <div style={{ padding: '2rem', background: '#1a1a1a', minHeight: '100vh', color: '#fff' }}>
        Loading listeners...
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
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Listener Management</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/map" style={{ color: '#4CAF50', textDecoration: 'none' }}>Map</Link>
          <Link to="/admin" style={{ color: '#4CAF50', textDecoration: 'none' }}>Dashboard</Link>
          <Link to="/traces" style={{ color: '#4CAF50', textDecoration: 'none' }}>Traces</Link>
          <Link to="/config" style={{ color: '#4CAF50', textDecoration: 'none' }}>Config</Link>
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

        {message && (
          <div style={{
            padding: '1rem',
            background: message.startsWith('Success') ? '#4CAF50' : '#f44336',
            color: 'white',
            borderRadius: '4px',
            marginBottom: '1rem'
          }}>
            {message}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ fontSize: '1rem', color: '#999' }}>
            Total: {listeners.length} | Active: {listeners.filter(l => l.active).length} | Inactive: {listeners.filter(l => !l.active).length}
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}
          >
            + Add Listener
          </button>
        </div>

        <div style={{ background: '#2a2a2a', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#333', borderBottom: '2px solid #444' }}>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Name</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>ID</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Last Seen</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Status</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Created</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {listeners.map((listener) => (
                  <tr key={listener.id} style={{ borderBottom: '1px solid #333', opacity: listener.active ? 1 : 0.5 }}>
                    <td style={{ padding: '1rem' }}>
                      {editingId === listener.id ? (
                        <input
                          type="text"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleUpdateListener(listener.id, editingName)
                            } else if (e.key === 'Escape') {
                              setEditingId(null)
                            }
                          }}
                          style={{
                            padding: '0.5rem',
                            background: '#1a1a1a',
                            color: '#fff',
                            border: '1px solid #4CAF50',
                            borderRadius: '4px',
                            width: '200px'
                          }}
                          autoFocus
                        />
                      ) : (
                        <span style={{ fontWeight: 'bold' }}>{listener.name}</span>
                      )}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#aaa' }}>
                          {truncateId(listener.id)}
                        </span>
                        <button
                          onClick={() => copyListenerId(listener.id)}
                          style={{
                            padding: '0.3rem 0.6rem',
                            background: '#2196F3',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.75rem'
                          }}
                          title="Copy full ID"
                        >
                          Copy ID
                        </button>
                      </div>
                    </td>
                    <td style={{ padding: '1rem', fontSize: '0.85rem' }}>
                      {formatDate(listener.last_seen)}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <span style={{
                        padding: '0.25rem 0.75rem',
                        background: listener.active ? '#4CAF5033' : '#44444433',
                        color: listener.active ? '#4CAF50' : '#999',
                        borderRadius: '12px',
                        fontSize: '0.8rem',
                        fontWeight: 'bold'
                      }}>
                        {listener.active ? '● Active' : '○ Inactive'}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#aaa' }}>
                      {new Date(listener.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      {listener.active && (
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {editingId === listener.id ? (
                            <>
                              <button
                                onClick={() => handleUpdateListener(listener.id, editingName)}
                                style={{
                                  padding: '0.4rem 0.8rem',
                                  background: '#4CAF50',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.85rem'
                                }}
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingId(null)}
                                style={{
                                  padding: '0.4rem 0.8rem',
                                  background: '#555',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.85rem'
                                }}
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => {
                                  setEditingId(listener.id)
                                  setEditingName(listener.name)
                                }}
                                style={{
                                  padding: '0.4rem 0.8rem',
                                  background: '#2196F3',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.85rem'
                                }}
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => setDeleteConfirmId(listener.id)}
                                style={{
                                  padding: '0.4rem 0.8rem',
                                  background: '#f44336',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '0.85rem'
                                }}
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {listeners.length === 0 && (
          <div style={{
            padding: '3rem',
            textAlign: 'center',
            color: '#999',
            fontSize: '1.1rem'
          }}>
            No listeners found. Click "Add Listener" to create one.
          </div>
        )}
      </div>

      {/* Add Listener Modal */}
      {showAddModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#2a2a2a',
            padding: '2rem',
            borderRadius: '8px',
            minWidth: '400px',
            maxWidth: '500px'
          }}>
            <h2 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Add New Listener</h2>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#aaa' }}>
                Listener Name
              </label>
              <input
                type="text"
                value={newListenerName}
                onChange={(e) => setNewListenerName(e.target.value)}
                placeholder="e.g., Listener-North"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#1a1a1a',
                  color: '#fff',
                  border: '1px solid #444',
                  borderRadius: '4px',
                  fontSize: '1rem'
                }}
                autoFocus
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button
                onClick={() => {
                  setShowAddModal(false)
                  setNewListenerName('')
                }}
                disabled={creating}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#555',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: creating ? 'not-allowed' : 'pointer',
                  fontSize: '1rem'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateListener}
                disabled={creating || !newListenerName.trim()}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: creating || !newListenerName.trim() ? '#333' : '#4CAF50',
                  color: creating || !newListenerName.trim() ? '#666' : 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: creating || !newListenerName.trim() ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold'
                }}
              >
                {creating ? 'Creating...' : 'Create Listener'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Key Display Modal */}
      {showApiKeyModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#2a2a2a',
            padding: '2rem',
            borderRadius: '8px',
            minWidth: '500px',
            maxWidth: '600px',
            border: '2px solid #4CAF50'
          }}>
            <h2 style={{ marginTop: 0, marginBottom: '1rem', color: '#4CAF50' }}>⚠️  Listener Created Successfully</h2>

            <div style={{
              background: '#3a3a00',
              border: '2px solid #ffeb3b',
              borderRadius: '4px',
              padding: '1rem',
              marginBottom: '1.5rem'
            }}>
              <p style={{ margin: 0, color: '#ffeb3b', fontWeight: 'bold', fontSize: '1.1rem' }}>
                IMPORTANT: Save your API key now!
              </p>
              <p style={{ margin: '0.5rem 0 0 0', color: '#ffeb3b', fontSize: '0.95rem' }}>
                This is the only time it will be displayed. You cannot retrieve it later.
              </p>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: '#aaa', fontSize: '0.9rem' }}>
                API Key:
              </label>
              <div style={{
                background: '#1a1a1a',
                padding: '1rem',
                borderRadius: '4px',
                border: '1px solid #444',
                fontFamily: 'monospace',
                fontSize: '0.95rem',
                wordBreak: 'break-all',
                color: '#4CAF50'
              }}>
                {newApiKey}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button
                onClick={copyToClipboard}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#2196F3',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold'
                }}
              >
                📋 Copy to Clipboard
              </button>
              <button
                onClick={() => {
                  setShowApiKeyModal(false)
                  setNewApiKey('')
                }}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold'
                }}
              >
                I've Saved It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#2a2a2a',
            padding: '2rem',
            borderRadius: '8px',
            minWidth: '400px',
            maxWidth: '500px'
          }}>
            <h2 style={{ marginTop: 0, marginBottom: '1rem', color: '#f44336' }}>Confirm Deactivation</h2>
            <p style={{ marginBottom: '1.5rem', color: '#ccc' }}>
              Are you sure you want to deactivate listener "{listeners.find(l => l.id === deleteConfirmId)?.name}"?
            </p>
            <p style={{ marginBottom: '1.5rem', color: '#999', fontSize: '0.9rem' }}>
              The listener will be deactivated but not deleted. Historical data will be preserved.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleting}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#555',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: deleting ? 'not-allowed' : 'pointer',
                  fontSize: '1rem'
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteListener(deleteConfirmId)}
                disabled={deleting}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: deleting ? '#333' : '#f44336',
                  color: deleting ? '#666' : 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: deleting ? 'not-allowed' : 'pointer',
                  fontSize: '1rem',
                  fontWeight: 'bold'
                }}
              >
                {deleting ? 'Deactivating...' : 'Deactivate Listener'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

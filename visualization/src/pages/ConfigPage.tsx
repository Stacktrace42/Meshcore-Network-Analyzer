import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface ConfigPageProps {
  apiKey: string
  onLogout: () => void
}

interface ConfigValue {
  key: string
  value: string
  value_type: string
  description: string
  updated_at: string
}

interface ConfigUpdate {
  [key: string]: string
}

// Use relative URL so nginx can proxy to processing service
const API_BASE_URL = ''

export default function ConfigPage({ apiKey, onLogout }: ConfigPageProps) {
  const [configs, setConfigs] = useState<ConfigValue[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [editedValues, setEditedValues] = useState<ConfigUpdate>({})
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  useEffect(() => {
    fetchConfigs()
  }, [])

  const fetchConfigs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/config`, {
        headers: {
          'Authorization': `Bearer ${apiKey}`
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch configurations')
      }

      const data = await response.json()
      setConfigs(data.configs)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleValueChange = (key: string, value: string) => {
    setEditedValues(prev => ({
      ...prev,
      [key]: value
    }))
  }

  const handleSave = async () => {
    if (Object.keys(editedValues).length === 0) {
      setSaveMessage('No changes to save')
      return
    }

    setSaving(true)
    setSaveMessage(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/config`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editedValues)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update configuration')
      }

      const result = await response.json()
      setSaveMessage(`Success: ${result.message}`)
      setEditedValues({})

      // Refresh configs
      await fetchConfigs()
    } catch (err) {
      setSaveMessage(`Error: ${err instanceof Error ? err.message : 'An error occurred'}`)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setEditedValues({})
    setSaveMessage(null)
  }

  const getCurrentValue = (config: ConfigValue): string => {
    return editedValues[config.key] !== undefined ? editedValues[config.key] : config.value
  }

  const hasChanges = Object.keys(editedValues).length > 0

  if (loading) {
    return (
      <div style={{ padding: '2rem', background: '#1a1a1a', minHeight: '100vh', color: '#fff' }}>
        Loading configuration...
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
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>System Configuration</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/map" style={{ color: '#4CAF50', textDecoration: 'none' }}>Map</Link>
          <Link to="/admin" style={{ color: '#4CAF50', textDecoration: 'none' }}>Dashboard</Link>
          <Link to="/traces" style={{ color: '#4CAF50', textDecoration: 'none' }}>Traces</Link>
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

        {saveMessage && (
          <div style={{
            padding: '1rem',
            background: saveMessage.startsWith('Success') ? '#4CAF50' : saveMessage.startsWith('Error') ? '#f44336' : '#2196F3',
            color: 'white',
            borderRadius: '4px',
            marginBottom: '1rem'
          }}>
            {saveMessage}
          </div>
        )}

        <div style={{ background: '#2a2a2a', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#333', borderBottom: '2px solid #444' }}>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Configuration Key</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Value</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Type</th>
                  <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.9rem', color: '#999' }}>Description</th>
                </tr>
              </thead>
              <tbody>
                {configs.map((config) => (
                  <tr key={config.key} style={{ borderBottom: '1px solid #333' }}>
                    <td style={{ padding: '1rem', fontFamily: 'monospace', fontSize: '0.9rem' }}>
                      {config.key}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <input
                        type={config.value_type === 'int' || config.value_type === 'float' ? 'number' : 'text'}
                        value={getCurrentValue(config)}
                        onChange={(e) => handleValueChange(config.key, e.target.value)}
                        step={config.value_type === 'float' ? '0.1' : '1'}
                        style={{
                          width: '150px',
                          padding: '0.5rem',
                          background: '#1a1a1a',
                          color: '#fff',
                          border: '1px solid #444',
                          borderRadius: '4px'
                        }}
                      />
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <span style={{
                        padding: '0.25rem 0.5rem',
                        background: '#444',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        color: '#aaa'
                      }}>
                        {config.value_type}
                      </span>
                    </td>
                    <td style={{ padding: '1rem', fontSize: '0.85rem', color: '#999' }}>
                      {config.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button
            onClick={handleReset}
            disabled={!hasChanges || saving}
            style={{
              padding: '0.75rem 1.5rem',
              background: !hasChanges || saving ? '#333' : '#555',
              color: !hasChanges || saving ? '#666' : '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: !hasChanges || saving ? 'not-allowed' : 'pointer',
              fontSize: '1rem'
            }}
          >
            Reset Changes
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            style={{
              padding: '0.75rem 1.5rem',
              background: !hasChanges || saving ? '#333' : '#4CAF50',
              color: !hasChanges || saving ? '#666' : '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: !hasChanges || saving ? 'not-allowed' : 'pointer',
              fontSize: '1rem',
              fontWeight: 'bold'
            }}
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

        <div style={{
          marginTop: '2rem',
          padding: '1rem',
          background: '#3a3a00',
          border: '1px solid #666600',
          borderRadius: '4px',
          color: '#ffeb3b'
        }}>
          <strong>Note:</strong> Configuration changes take effect immediately for new operations.
          Some changes may require restarting the processing service for full effect.
        </div>
      </div>
    </div>
  )
}

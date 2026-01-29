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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
          'X-API-Key': apiKey
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
          'X-API-Key': apiKey,
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
      <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
        <div className="max-w-4xl mx-auto">
          <p>Loading configuration...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold">System Configuration</h1>
          <div className="flex gap-4">
            <Link to="/admin" className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded">
              Back to Admin
            </Link>
            <button
              onClick={onLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded"
            >
              Logout
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-900 border border-red-700 rounded">
            <p className="text-red-200">{error}</p>
          </div>
        )}

        {saveMessage && (
          <div className={`mb-4 p-4 rounded ${
            saveMessage.startsWith('Success')
              ? 'bg-green-900 border border-green-700 text-green-200'
              : saveMessage.startsWith('Error')
              ? 'bg-red-900 border border-red-700 text-red-200'
              : 'bg-blue-900 border border-blue-700 text-blue-200'
          }`}>
            <p>{saveMessage}</p>
          </div>
        )}

        <div className="bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-3 px-4">Configuration Key</th>
                <th className="text-left py-3 px-4">Value</th>
                <th className="text-left py-3 px-4">Type</th>
                <th className="text-left py-3 px-4">Description</th>
              </tr>
            </thead>
            <tbody>
              {configs.map((config) => (
                <tr key={config.key} className="border-b border-gray-700 hover:bg-gray-750">
                  <td className="py-3 px-4 font-mono text-sm">{config.key}</td>
                  <td className="py-3 px-4">
                    <input
                      type={config.value_type === 'int' || config.value_type === 'float' ? 'number' : 'text'}
                      value={getCurrentValue(config)}
                      onChange={(e) => handleValueChange(config.key, e.target.value)}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:border-blue-500"
                      step={config.value_type === 'float' ? '0.1' : '1'}
                    />
                  </td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 bg-gray-700 rounded text-xs">{config.value_type}</span>
                  </td>
                  <td className="py-3 px-4 text-sm text-gray-400">{config.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex justify-end gap-4">
          <button
            onClick={handleReset}
            disabled={!hasChanges || saving}
            className="px-6 py-2 bg-gray-700 hover:bg-gray-600 rounded disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Reset Changes
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

        <div className="mt-8 p-4 bg-yellow-900 border border-yellow-700 rounded">
          <p className="text-yellow-200 text-sm">
            <strong>Note:</strong> Configuration changes take effect immediately for new operations.
            Some changes may require restarting the processing service for full effect.
          </p>
        </div>
      </div>
    </div>
  )
}

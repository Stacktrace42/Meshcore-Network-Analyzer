import { useState } from 'react'

interface LoginProps {
  onLogin: (apiKey: string) => void
}

export default function Login({ onLogin }: LoginProps) {
  const [apiKey, setApiKey] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (apiKey.trim()) {
      onLogin(apiKey.trim())
    }
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      backgroundColor: '#1a1a1a'
    }}>
      <form onSubmit={handleSubmit} style={{
        background: '#2a2a2a',
        padding: '2rem',
        borderRadius: '8px',
        minWidth: '400px'
      }}>
        <h1 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          Meshcore Network Analyzer
        </h1>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="apiKey" style={{ display: 'block', marginBottom: '0.5rem' }}>
            API Key
          </label>
          <input
            id="apiKey"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your API key"
            style={{
              width: '100%',
              padding: '0.5rem',
              borderRadius: '4px',
              border: '1px solid #444',
              background: '#1a1a1a',
              color: 'white'
            }}
          />
        </div>
        <button
          type="submit"
          style={{
            width: '100%',
            padding: '0.75rem',
            background: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
        >
          Login
        </button>
      </form>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MapView from './pages/MapView'
import AdminDashboard from './pages/AdminDashboard'
import TracesPage from './pages/TracesPage'
import ConfigPage from './pages/ConfigPage'
import ListenersPage from './pages/ListenersPage'
import Login from './pages/Login'

function App() {
  const [apiKey, setApiKey] = useState<string>(() => {
    return localStorage.getItem('apiKey') || ''
  })

  useEffect(() => {
    if (apiKey) {
      localStorage.setItem('apiKey', apiKey)
    } else {
      localStorage.removeItem('apiKey')
    }
  }, [apiKey])

  const handleLogin = (key: string) => {
    setApiKey(key)
  }

  const handleLogout = () => {
    setApiKey('')
    localStorage.removeItem('apiKey')
  }

  if (!apiKey) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/map" replace />} />
        <Route path="/map" element={<MapView apiKey={apiKey} onLogout={handleLogout} />} />
        <Route path="/admin" element={<AdminDashboard apiKey={apiKey} onLogout={handleLogout} />} />
        <Route path="/traces" element={<TracesPage apiKey={apiKey} onLogout={handleLogout} />} />
        <Route path="/listeners" element={<ListenersPage apiKey={apiKey} onLogout={handleLogout} />} />
        <Route path="/config" element={<ConfigPage apiKey={apiKey} onLogout={handleLogout} />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import axios from 'axios'
import 'leaflet/dist/leaflet.css'

// Use relative URL so nginx can proxy to processing service
const API_URL = ''

// Component to automatically fit map bounds to show all repeaters (only on first load)
function MapBoundsHandler({ bounds }: { bounds: [[number, number], [number, number]] }) {
  const map = useMap()
  const [hasSetInitialBounds, setHasSetInitialBounds] = useState(false)

  useEffect(() => {
    // Only auto-zoom on the first load, not on subsequent data updates
    if (bounds && !hasSetInitialBounds) {
      map.fitBounds(bounds, { padding: [50, 50] })
      setHasSetInitialBounds(true)
    }
  }, [bounds, map, hasSetInitialBounds])

  return null
}

interface Repeater {
  id: string
  hash: string
  name?: string
  gps_lat?: number
  gps_lon?: number
  estimated_gps_lat?: number
  estimated_gps_lon?: number
  position_confidence?: string
  triangulation_neighbors?: string[]
  last_seen: string
}

interface GraphEdge {
  id: number
  from_repeater_id: string
  to_repeater_id: string
  message_count: number
  avg_snr?: number
  sample_path?: string[]
  last_trace_at?: string
  last_trace_path?: string
}

interface GraphData {
  repeaters: Repeater[]
  edges: GraphEdge[]
}

interface MapViewProps {
  apiKey: string
  onLogout: () => void
}

// SNR to color mapping - adapts to light/dark mode
function snrToColor(snr?: number | null, darkMode: boolean = false): string {
  // Gray for null/undefined SNR (no trace data yet)
  if (snr === null || snr === undefined) return '#808080'

  if (darkMode) {
    // Brighter colors for dark mode
    if (snr < 0) return '#ff4444'  // Bright red
    if (snr < 4) return '#ff9944'  // Bright orange
    if (snr < 8) return '#ffff44'  // Bright yellow
    if (snr < 10) return '#88ff44' // Bright light green
    return '#44ff44'               // Bright green
  } else {
    // Darker colors for light mode
    if (snr < 0) return '#cc0000'  // Dark red
    if (snr < 4) return '#cc6600'  // Dark orange
    if (snr < 8) return '#cccc00'  // Dark yellow
    if (snr < 10) return '#66cc00' // Dark light green
    return '#00cc00'               // Dark green
  }
}

// Create custom circle icon with hash label
function createRepeaterIcon(hash: string, darkMode: boolean, isEstimated: boolean = false): L.DivIcon {
  const hashText = hash.replace('0x', '')
  const bgColor = isEstimated ? (darkMode ? '#ff8c00' : '#ff8c00') : (darkMode ? '#66bb6a' : '#4CAF50')
  const borderStyle = isEstimated ? '3px dashed' : '3px solid'

  return L.divIcon({
    html: `
      <div style="
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: ${bgColor};
        border: ${borderStyle} ${darkMode ? '#2a2a2a' : '#ffffff'};
        box-shadow: 0 2px 8px rgba(0,0,0,${darkMode ? '0.7' : '0.3'});
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 11px;
        color: white;
        font-family: monospace;
        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
      ">
        ${hashText}
      </div>
    `,
    className: 'custom-repeater-icon',
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
  })
}

export default function MapView({ apiKey, onLogout }: MapViewProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [darkMode, setDarkMode] = useState(() => {
    // Load dark mode preference from localStorage
    const saved = localStorage.getItem('mapDarkMode')
    return saved ? JSON.parse(saved) : true // Default to dark mode
  })

  // Save dark mode preference
  useEffect(() => {
    localStorage.setItem('mapDarkMode', JSON.stringify(darkMode))
  }, [darkMode])

  const fetchGraphData = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/graph`, {
        headers: { 'Authorization': `Bearer ${apiKey}` }
      })
      setGraphData(response.data)
      setError(null)
    } catch (err) {
      setError('Failed to fetch graph data')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGraphData()
    const interval = setInterval(fetchGraphData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [apiKey])

  if (loading) {
    return <div style={{ padding: '2rem' }}>Loading...</div>
  }

  if (error) {
    return <div style={{ padding: '2rem', color: 'red' }}>{error}</div>
  }

  // Filter repeaters with valid GPS coordinates or estimated positions (exclude 0,0 and near 0,0)
  const repeatersWithGPS = graphData?.repeaters.filter(r => {
    const lat = r.gps_lat ?? r.estimated_gps_lat
    const lon = r.gps_lon ?? r.estimated_gps_lon
    return lat != null && lon != null && !(Math.abs(lat) < 0.1 && Math.abs(lon) < 0.1)
  }) || []

  // Calculate bounds to fit all repeaters
  const defaultCenter: [number, number] = [51.505, 6.5] // Center of NRW region
  const defaultBounds: [[number, number], [number, number]] = [
    [50.3, 5.8], // Southwest corner
    [52.5, 9.5]  // Northeast corner
  ]

  let bounds: [[number, number], [number, number]] = defaultBounds
  let center: [number, number] = defaultCenter

  if (repeatersWithGPS.length > 0) {
    // Calculate actual bounds from repeaters (use estimated position if GPS not available)
    const lats = repeatersWithGPS.map(r => r.gps_lat ?? r.estimated_gps_lat!)
    const lons = repeatersWithGPS.map(r => r.gps_lon ?? r.estimated_gps_lon!)

    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)

    // Add 5% padding
    const latPadding = (maxLat - minLat) * 0.05
    const lonPadding = (maxLon - minLon) * 0.05

    bounds = [
      [minLat - latPadding, minLon - lonPadding],
      [maxLat + latPadding, maxLon + lonPadding]
    ]

    center = [(minLat + maxLat) / 2, (minLon + maxLon) / 2]
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#2a2a2a',
        padding: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Meshcore Network Map</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button
            onClick={() => setDarkMode(!darkMode)}
            style={{
              padding: '0.5rem 1rem',
              background: darkMode ? '#444' : '#ddd',
              color: darkMode ? '#fff' : '#333',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '14px'
            }}
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {darkMode ? '🌙' : '☀️'} {darkMode ? 'Dark' : 'Light'}
          </button>
          <Link to="/admin" style={{ color: '#4CAF50', textDecoration: 'none' }}>
            Admin
          </Link>
          <Link to="/traces" style={{ color: '#4CAF50', textDecoration: 'none' }}>
            Traces
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

      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer center={center} zoom={10} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url={darkMode
              ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            }
            attribution={darkMode
              ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
              : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }
          />

          {/* Auto-fit map to show all repeaters */}
          <MapBoundsHandler bounds={bounds} />

          {/* Render edges */}
          {graphData?.edges.map(edge => {
            const fromRepeater = graphData.repeaters.find(r => r.id === edge.from_repeater_id)
            const toRepeater = graphData.repeaters.find(r => r.id === edge.to_repeater_id)

            // Use estimated position if GPS not available
            const fromLat = fromRepeater?.gps_lat ?? fromRepeater?.estimated_gps_lat
            const fromLon = fromRepeater?.gps_lon ?? fromRepeater?.estimated_gps_lon
            const toLat = toRepeater?.gps_lat ?? toRepeater?.estimated_gps_lat
            const toLon = toRepeater?.gps_lon ?? toRepeater?.estimated_gps_lon

            if (!fromRepeater || !toRepeater || !fromLat || !toLat) return null

            const positions: [number, number][] = [
              [fromLat, fromLon!],
              [toLat, toLon!]
            ]

            const weight = Math.min(Math.max(edge.message_count / 10, 2), 10)
            const color = snrToColor(edge.avg_snr, darkMode)

            return (
              <Polyline
                key={edge.id}
                positions={positions}
                color={color}
                weight={weight}
                opacity={darkMode ? 0.9 : 0.8}
              >
                <Popup>
                  <div style={{ minWidth: '250px', maxWidth: '400px' }}>
                    <strong style={{ fontSize: '14px', color: '#2196F3' }}>Network Edge</strong>
                    <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #ddd' }} />

                    <div style={{ marginBottom: '8px' }}>
                      <strong>From:</strong> {fromRepeater.name || 'Unnamed'}
                      <br />
                      <span style={{ fontSize: '12px', color: '#666' }}>
                        Hash: {fromRepeater.hash}
                      </span>
                    </div>

                    <div style={{ marginBottom: '8px' }}>
                      <strong>To:</strong> {toRepeater.name || 'Unnamed'}
                      <br />
                      <span style={{ fontSize: '12px', color: '#666' }}>
                        Hash: {toRepeater.hash}
                      </span>
                    </div>

                    <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #ddd' }} />

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                      <div>
                        <strong>Messages:</strong>
                        <br />
                        <span style={{ fontSize: '18px', color: '#4CAF50' }}>{edge.message_count}</span>
                      </div>
                      <div>
                        <strong>Avg SNR:</strong>
                        <br />
                        {edge.avg_snr !== null && edge.avg_snr !== undefined ? (
                          <span style={{ fontSize: '18px', color: color }}>
                            {edge.avg_snr.toFixed(2)} dB
                          </span>
                        ) : (
                          <span style={{ fontSize: '14px', color: '#808080' }}>
                            No trace data
                          </span>
                        )}
                      </div>
                    </div>

                    {edge.sample_path && edge.sample_path.length > 0 && (
                      <>
                        <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #ddd' }} />
                        <div>
                          <strong>Example Path ({edge.sample_path.length} hops):</strong>
                          <div style={{
                            marginTop: '4px',
                            fontSize: '11px',
                            color: '#555',
                            backgroundColor: '#f5f5f5',
                            padding: '8px',
                            borderRadius: '4px',
                            maxHeight: '120px',
                            overflowY: 'auto',
                            fontFamily: 'monospace',
                            lineHeight: '1.6'
                          }}>
                            {edge.sample_path.map((hop, idx) => (
                              <span key={idx}>
                                <span style={{ color: idx === 0 ? '#2196F3' : idx === edge.sample_path!.length - 1 ? '#4CAF50' : '#666' }}>
                                  {hop.replace('0x', '')}
                                </span>
                                {idx < edge.sample_path!.length - 1 && <span style={{ color: '#999' }}> → </span>}
                              </span>
                            ))}
                          </div>
                        </div>
                      </>
                    )}

                    {edge.last_trace_path && (
                      <>
                        <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #ddd' }} />
                        <div>
                          <strong style={{ color: '#2196F3' }}>Last Successful Trace:</strong>
                          <div style={{
                            marginTop: '4px',
                            fontSize: '11px',
                            color: '#555',
                            backgroundColor: '#e3f2fd',
                            padding: '8px',
                            borderRadius: '4px',
                            fontFamily: 'monospace',
                            lineHeight: '1.6'
                          }}>
                            {edge.last_trace_path}
                          </div>
                          {edge.last_trace_at && (
                            <div style={{ marginTop: '4px', fontSize: '10px', color: '#666' }}>
                              Verified: {new Date(edge.last_trace_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                      </>
                    )}

                    <div style={{ marginTop: '8px', fontSize: '11px', color: '#999' }}>
                      Edge ID: {edge.id}
                    </div>
                  </div>
                </Popup>
              </Polyline>
            )
          })}

          {/* Render repeaters */}
          {repeatersWithGPS.map(repeater => {
            const isEstimated = !repeater.gps_lat && repeater.estimated_gps_lat != null
            const lat = repeater.gps_lat ?? repeater.estimated_gps_lat!
            const lon = repeater.gps_lon ?? repeater.estimated_gps_lon!

            return (
              <Marker
                key={repeater.id}
                position={[lat, lon]}
                icon={createRepeaterIcon(repeater.hash, darkMode, isEstimated)}
              >
                <Popup>
                  <div style={{ minWidth: '200px' }}>
                    <strong style={{ fontSize: '14px', color: isEstimated ? '#ff8c00' : '#4CAF50' }}>
                      {repeater.name || 'Unnamed Repeater'}
                    </strong>
                    <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #ddd' }} />
                    <div style={{ fontSize: '12px', lineHeight: '1.6' }}>
                      <strong>Hash:</strong> {repeater.hash.replace('0x', '')}
                      <br />
                      <strong>Position:</strong>{' '}
                      {isEstimated ? (
                        <span style={{ color: '#ff8c00' }}>
                          Estimated from {repeater.triangulation_neighbors?.length || 0} neighbors
                        </span>
                      ) : (
                        <span style={{ color: '#4CAF50' }}>Known from GPS</span>
                      )}
                      <br />
                      <strong>Last seen:</strong>
                      <br />
                      {new Date(repeater.last_seen).toLocaleString()}
                    </div>
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>

        {/* Legend */}
        <div style={{
          position: 'absolute',
          bottom: '20px',
          right: '20px',
          background: darkMode ? 'rgba(42, 42, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          padding: '1rem',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          fontSize: '12px',
          zIndex: 1000,
          maxWidth: '250px'
        }}>
          <strong style={{ display: 'block', marginBottom: '8px', fontSize: '14px' }}>Legend</strong>

          <div style={{ marginBottom: '8px' }}>
            <strong>Repeaters:</strong>
            <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: darkMode ? '#66bb6a' : '#4CAF50',
                border: '2px solid white'
              }}></div>
              <span>Known GPS position</span>
            </div>
            <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: '#ff8c00',
                border: '2px dashed white'
              }}></div>
              <span>Triangulated position</span>
            </div>
          </div>

          <div>
            <strong>Edge Colors (SNR):</strong>
            <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: '#808080' }}></div>
                <span>No trace data</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: darkMode ? '#ff4444' : '#cc0000' }}></div>
                <span>&lt; 0 dB (poor)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: darkMode ? '#ff9944' : '#cc6600' }}></div>
                <span>0-4 dB (weak)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: darkMode ? '#ffff44' : '#cccc00' }}></div>
                <span>4-8 dB (fair)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: darkMode ? '#88ff44' : '#66cc00' }}></div>
                <span>8-10 dB (good)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '20px', height: '3px', background: darkMode ? '#44ff44' : '#00cc00' }}></div>
                <span>&gt; 10 dB (excellent)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

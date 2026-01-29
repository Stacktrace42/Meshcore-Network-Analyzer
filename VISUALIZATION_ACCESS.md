# Meshcore Network Analyzer - Visualization Access

## 🌐 Web Interface is Live!

The visualization web interface is now running and accessible.

### Access URLs

**Main Application:**
```
http://localhost:3000
```

**API Documentation:**
```
http://localhost:8000/docs
```

**Health Check:**
```
http://localhost:8000/health
```

## Login Credentials

When you access http://localhost:3000, you'll be prompted for an API key.

**Use this Visualization API Key:**
```
ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE
```

Copy and paste this key into the login form.

## Features Available

### 1. Map View (Main Interface)
- **Interactive OpenStreetMap** showing the MeshCore network
- **Repeater Markers** with GPS coordinates
- **Path Lines** between repeaters:
  - **Line Color** = SNR quality
    - 🔴 Red: Poor signal (SNR < 0 dB)
    - 🟠 Orange: Fair signal (0-4 dB)
    - 🟡 Yellow: Good signal (4-8 dB)
    - 🟢 Light Green: Very good (8-10 dB)
    - 🟢 Green: Excellent (> 10 dB)
  - **Line Thickness** = Message count (1-10px)
- **Click on markers** to see repeater details
- **Click on lines** to see edge statistics
- **Auto-refresh** every 30 seconds

### 2. Admin Dashboard
- System statistics
- Active listeners
- Total repeaters and paths
- Trace command status
- Real-time updates every 10 seconds

## Navigation

Once logged in:
- **"Map View"** button (top right) - Return to main map
- **"Admin"** button (top right) - View statistics
- **"Logout"** button (top right) - Log out

## Current Data Status

Based on your system (as of 2026-01-28 17:10):

```
✅ 1 Active Listener (connected to /dev/ttyUSB0)
✅ 1000 Messages pulled from device storage
⏳ Processing messages for path information
⏳ Building network graph
```

**Note:** The map will initially be empty until:
1. Messages are processed for path information
2. Repeater advertisements are captured
3. The graph builder runs (every 5 minutes)

## Troubleshooting

### Can't Access http://localhost:3000
```bash
# Check if visualization is running
sudo docker compose ps visualization

# Check logs
sudo docker compose logs visualization

# Restart if needed
sudo docker compose restart visualization
```

### Login Not Working
- Make sure you're using the correct API key (see above)
- Copy/paste to avoid typos
- No spaces before or after the key

### Map Not Loading
- Check if the graph has been built:
```bash
curl -s http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

- Wait 5 minutes for the first graph rebuild
- Check if repeaters have been discovered:
```bash
curl -s http://localhost:8000/api/v1/repeaters \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

### No Repeaters Showing
The system needs to receive:
1. **Repeater advertisements** (with GPS coordinates)
2. **Message packets** (with path information)

Monitor listener logs:
```bash
sudo docker compose logs -f listener | grep -E "(Advertisement|repeater|contact)"
```

## Testing the Visualization

### Check Current Stats
```bash
curl -s http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | python3 -m json.tool
```

### Check Network Graph
```bash
curl -s http://localhost:8000/api/v1/graph \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | python3 -m json.tool
```

### Check Repeaters
```bash
curl -s http://localhost:8000/api/v1/repeaters \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | python3 -m json.tool
```

## Service Ports

All services are now running:

| Service        | Port | URL                       |
|----------------|------|---------------------------|
| Visualization  | 3000 | http://localhost:3000     |
| Processing API | 8000 | http://localhost:8000     |
| PostgreSQL     | 5432 | localhost:5432 (internal) |

## System Architecture

```
┌─────────────────────┐
│  Browser (You)      │
│  localhost:3000     │
└──────────┬──────────┘
           │ HTTP
           ↓
┌─────────────────────┐
│  Visualization      │
│  (React + Leaflet)  │
│  nginx:80           │
└──────────┬──────────┘
           │ REST API
           ↓
┌─────────────────────┐     ┌─────────────────────┐
│  Processing API     │────→│  PostgreSQL         │
│  FastAPI:8000       │     │  Database           │
└──────────┬──────────┘     └─────────────────────┘
           ↑
           │ REST API
           │
┌──────────┴──────────┐
│  Listener           │
│  Python Service     │
└──────────┬──────────┘
           │ Serial
           ↓
┌─────────────────────┐
│  MeshCore Device    │
│  /dev/ttyUSB0       │
└─────────────────────┘
```

## Next Steps

1. **Open your browser** to http://localhost:3000
2. **Enter the API key** when prompted
3. **Wait for data** to populate (network activity or message processing)
4. **Explore the map** as repeaters and paths appear
5. **Check Admin dashboard** for statistics

Enjoy your MeshCore network visualization! 🗺️

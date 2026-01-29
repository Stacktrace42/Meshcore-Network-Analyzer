# Meshcore Network Analyzer - Quick Start Guide

## 🎉 System Status: OPERATIONAL

All services are running and connected to your MeshCore hardware on `/dev/ttyUSB0`!

### Current Status

```
✅ PostgreSQL Database - Running & Healthy
✅ Processing API - Running on http://localhost:8000
✅ Listener Service - Connected to /dev/ttyUSB0
✅ 1 Active Listener Registered
✅ Waiting for MeshCore network traffic
```

## API Keys

**Admin API Key:**
```
meshcore-admin-key-2024-secure
```

**Listener API Key:**
```
sK6ghqcWxB2ZH01fxQ1t_abtp7gSGAO7GlTx7VBf0Hg
```

**Visualization API Key:**
```
ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE
```

## Quick Commands

### Check Service Status
```bash
cd "/home/soemers/project/Meshcore Network Analyzer"
sudo docker compose ps
```

### View Logs
```bash
# All services
sudo docker compose logs -f

# Specific service
sudo docker compose logs -f listener
sudo docker compose logs -f processing
```

### Monitor for Packets
```bash
sudo docker compose logs -f listener | grep -E "(Advertisement|Message|contact)"
```

### Check System Stats
```bash
curl -s http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

### Access API Documentation
Open in browser: http://localhost:8000/docs

### Check Health
```bash
curl http://localhost:8000/health
```

## What's Happening Now

1. **Listener** is connected to your MeshCore device at `/dev/ttyUSB0`
2. **Listening** for:
   - Repeater advertisements (with GPS coordinates)
   - Message packets (with path information)
   - ACK packets (with SNR/RSSI data)

3. **Processing** will:
   - Store received data in PostgreSQL
   - Build network graph every 5 minutes
   - Schedule trace commands to verify paths

4. **Data Flow:**
   ```
   MeshCore Hardware → Listener → Processing API → Database
   ```

## When Network Activity Occurs

As soon as repeaters start broadcasting or messages are sent through the network:

1. Repeaters will appear in the database
2. Paths between repeaters will be captured
3. The graph will be automatically built
4. Trace commands will be scheduled to verify paths

## Accessing Data

### Get All Repeaters
```bash
curl -s http://localhost:8000/api/v1/repeaters \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

### Get Network Graph
```bash
curl -s http://localhost:8000/api/v1/graph \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

### List Listeners
```bash
curl -s http://localhost:8000/api/v1/admin/listeners \
  -H "Authorization: Bearer meshcore-admin-key-2024-secure"
```

## Troubleshooting

### Restart Services
```bash
sudo docker compose restart listener
sudo docker compose restart processing
```

### Rebuild After Code Changes
```bash
sudo docker compose build listener
sudo docker compose build processing
sudo docker compose up -d
```

### Check Database Connection
```bash
sudo docker compose exec postgres psql -U meshcore -d meshcore_analyzer -c "SELECT COUNT(*) FROM listeners;"
```

### View All Logs
```bash
sudo docker compose logs --tail=100
```

## Next Steps

### To Build Visualization UI (Optional)
The visualization is still building. Once complete, you can access it at:
```
http://localhost:3000
```

Login with the visualization API key: `ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE`

### Generate Test Data
If you want to test without waiting for network traffic, you can manually insert test data via the API.

## System Architecture

```
┌─────────────────────┐
│  MeshCore Hardware  │
│    (/dev/ttyUSB0)   │
└──────────┬──────────┘
           │ USB Serial
           ↓
┌─────────────────────┐
│   Listener Service  │
│   - Packet Capture  │
│   - Path Extraction │
└──────────┬──────────┘
           │ HTTP REST
           ↓
┌─────────────────────┐     ┌─────────────────────┐
│ Processing Service  │────→│   PostgreSQL DB     │
│  - Graph Builder    │     │  - Repeaters        │
│  - Trace Scheduler  │     │  - Paths            │
│  - REST API         │     │  - Graph Edges      │
└─────────────────────┘     └─────────────────────┘
```

## Need Help?

- API Documentation: http://localhost:8000/docs
- Check logs: `sudo docker compose logs -f`
- System health: `curl http://localhost:8000/health`
- Stats: `curl -s http://localhost:8000/api/v1/stats -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"`

# Meshcore Network Analyzer

A web application that visualizes traffic and signal strength between repeaters of the MeshCore network on a map. The system captures network data by listening to traffic and actively probing the network with trace commands.

## Overview

The Meshcore Network Analyzer consists of three Docker containers:

1. **Listener** - Connects to MeshCore hardware via USB, captures packets and path information
2. **Processing** - Central API server with PostgreSQL database, handles graph building and trace scheduling
3. **Visualization** - React web UI with OpenStreetMap for visualizing the network

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Listener   │────────>│ Processing  │<────────│Visualization│
│   (Python)  │  REST   │  (FastAPI)  │   REST  │   (React)   │
│             │         │             │         │             │
│ - USB/ttyUSB│         │ - PostgreSQL│         │ - Leaflet   │
│ - meshcore_py│        │ - Graph     │         │ - Map View  │
│ - Packet    │         │ - Traces    │         │ - Admin UI  │
│   capture   │         │ - API Keys  │         │             │
└─────────────┘         └─────────────┘         └─────────────┘
       │
       │
       v
┌─────────────┐
│  MeshCore   │
│   Hardware  │
│ (/dev/ttyUSB)│
└─────────────┘
```

## Features

### Data Collection
- **Real-time packet capture** from MeshCore network traffic
- **Path tracking** with SNR and RSSI measurements
- **Repeater collision resolution** using GPS-based neighbor distance
- **Automatic gateway selection** - Best repeater chosen by SNR

### Active Network Probing
- **Loop-based trace execution** - Traces follow Gateway → Destination → Source → Gateway pattern
- **Automatic trace scheduling** with intelligent deduplication
- **Trace cleanup** - Auto-removal of stale, expired, and old traces
- **Per-listener limits** - Prevents queue buildup (max 50 pending per listener)
- **Formatted trace results** - Paths stored as "0xa0(-3.4)→0x41(12.0)" with SNR values

### Interactive Map Visualization
- **Auto-focus** - Map automatically zooms to show all valid repeaters
- **Dark/Light mode** toggle
- **Repeater markers** with hash labels
- **Path lines** colored by SNR:
  - Red: SNR < 0 dB (poor)
  - Orange: SNR 0-4 dB (fair)
  - Yellow: SNR 4-8 dB (good)
  - Light Green: SNR 8-10 dB (very good)
  - Green: SNR > 10 dB (excellent)
- **Line thickness** representing message count
- **Edge popups** showing:
  - From/To repeaters
  - Message count and average SNR
  - Example observed path
  - **Last successful trace** with formatted path and timestamp
  - Edge ID

### Admin Dashboard
- **System statistics** - Repeaters, listeners, paths, traces
- **Listener management** - Register and manage network listeners
- **Trace management** - View, filter, pause/resume trace scheduling
- **API key generation** - Admin, listener, and visualization keys

## Prerequisites

- Docker and Docker Compose
- MeshCore hardware device connected via USB (typically `/dev/ttyUSB0`)
- Linux host (for USB device passthrough)

## Quick Start

### 1. Clone and Configure

```bash
cd "Meshcore Network Analyzer"
cp .env.example .env
```

### 2. Edit Configuration

Edit `.env` and set:

```bash
# Database password
DB_PASSWORD=your-secure-database-password

# Admin API key (use a strong random key)
ADMIN_API_KEY=your-secure-admin-api-key

# Listener configuration
LISTENER_ID=$(uuidgen)  # Generate a unique UUID
LISTENER_NAME="My Listener"
GPS_LAT=your-latitude
GPS_LON=your-longitude
DEVICE_PATH=/dev/ttyUSB0  # Your MeshCore device path
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Initialize the System

#### Create Listener API Key

```bash
curl -X POST http://localhost:8000/api/v1/admin/listeners \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Listener",
    "gps_lat": YOUR_LAT,
    "gps_lon": YOUR_LON
  }'
```

Save the returned `api_key` and update `.env`:

```bash
LISTENER_API_KEY=<api_key_from_response>
```

#### Create Visualization API Key

```bash
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_type": "visualization",
    "description": "Web UI access"
  }'
```

### 5. Restart Listener

```bash
docker-compose restart listener
```

### 6. Access the Application

- **Visualization UI**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage

### Viewing the Network Map

1. Open http://localhost:3000
2. Enter your visualization API key
3. View the interactive map showing:
   - Repeater nodes with names and hashes
   - Path connections between repeaters
   - SNR-based coloring (red to green)
   - Message count-based line thickness

### Admin Dashboard

Access the admin dashboard to:

- View system statistics
- Manage listeners
- Configure trace scheduling
- Monitor trace execution
- Generate new API keys

### API Endpoints

#### Listener Endpoints

```bash
# Submit data (path, contact, trace result)
POST /api/v1/listener/data

# Get pending traces
GET /api/v1/listener/traces/pending

# Submit trace result
POST /api/v1/listener/traces/{id}/result
```

#### Visualization Endpoints

```bash
# Get network graph
GET /api/v1/graph?week_number=5

# Get all repeaters
GET /api/v1/repeaters

# Get system statistics
GET /api/v1/stats
```

#### Admin Endpoints

```bash
# Create listener
POST /api/v1/admin/listeners

# List listeners
GET /api/v1/admin/listeners

# Create API key
POST /api/v1/admin/api-keys

# View trace schedule
GET /api/v1/admin/trace-schedule

# Get trace configuration
GET /api/v1/admin/trace-config
```

## How the Trace System Works

The trace system actively probes the network to verify paths between repeaters. Here's how it works:

### Loop-Based Tracing

All traces must form a **loop** through the gateway repeater to ensure responses can be received:

1. **Gateway Selection** - The listener automatically selects the nearest repeater with best SNR as the gateway
2. **Trace Path Construction** - To verify edge A→B with gateway X:
   - Trace path: `X → B → A → X` (loop back to gateway)
   - This verifies the path exists and ensures we can receive the response
3. **Response Reception** - The response packet must physically reach our device through the gateway

### Example

To verify edge `0x4d → 0xd7` with gateway `0x84`:
- **Trace sent:** `84,d7,4d,84` (gateway → dest → source → gateway)
- **Response received:** With SNR values for each hop
- **Result stored:** `0x84(-3.4)→0xd7(12.0)→0x4d(8.5)→0x84(10.2)`

### Scheduling and Cleanup

- **Automatic scheduling** - Traces scheduled for all observed edges once per verification interval (default: 24h)
- **Intelligent deduplication** - Prevents duplicate traces (checks pending, in_progress, and recent traces)
- **Per-listener limits** - Maximum 50 pending traces per listener (configurable via `MAX_PENDING_TRACES_PER_LISTENER`)
- **Automatic cleanup:**
  - Stale in_progress traces (over 5 minutes) → marked as failed
  - Expired pending traces (over 1 hour) → marked as failed
  - Old completed/failed traces (over 7 days) → deleted

### Trace Results

Successful trace results are:
1. **Stored in trace_schedule** - As JSON result with formatted path
2. **Created as Path entry** - Added to paths table for aggregation
3. **Updated in GraphEdge** - `last_trace_at` and `last_trace_path` columns updated
4. **Displayed on map** - Shown in edge popup as "Last Successful Trace"

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Key settings:**

- `TRACE_THROTTLE_SECONDS`: Minimum delay between traces (default: 30)
- `TRACE_VERIFICATION_INTERVAL_HOURS`: How often to verify each path (default: 24)
- `GRAPH_REBUILD_INTERVAL_MINUTES`: How often to rebuild the graph (default: 5)
- `POLL_INTERVAL_SECONDS`: How often listener polls for traces (default: 30)

### Database

The system uses PostgreSQL for storage with the following tables:

- `listeners` - Network nodes running the listener component
- `repeaters` - MeshCore repeaters discovered on the network
- `paths` - Observed packet paths with SNR/RSSI
- `graph_edges` - Computed network graph edges
- `trace_schedule` - Scheduled trace commands
- `api_keys` - API key authentication

### Repeater Hash Collision Resolution

MeshCore uses only the first byte of the public key to identify repeaters in paths. When multiple repeaters share the same hash, the system resolves the collision by:

1. Calculating geodesic distance to neighboring repeaters
2. Selecting the repeater closest to its path neighbors
3. Falling back to the first known repeater if GPS data is unavailable

## Development

### Project Structure

```
/
├── docker-compose.yml
├── .env
├── listener/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── device_manager.py
│       ├── packet_listener.py
│       ├── contact_manager.py
│       ├── api_client.py
│       └── trace_handler.py
├── processing/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── graph_builder.py
│       ├── trace_scheduler.py
│       ├── repeater_resolver.py
│       └── api/
│           ├── auth.py
│           ├── listeners.py
│           ├── visualization.py
│           └── admin.py
└── visualization/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.tsx
        ├── pages/
        ├── components/
        └── hooks/
```

### Running in Development Mode

To run individual components for development:

**Processing:**
```bash
cd processing
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql://... uvicorn src.main:app --reload
```

**Listener:**
```bash
cd listener
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

**Visualization:**
```bash
cd visualization
npm install
npm run dev
```

## Troubleshooting

### Listener can't connect to device

- Check device permissions: `sudo chmod 666 /dev/ttyUSB0`
- Verify device path: `ls -l /dev/ttyUSB*`
- Check listener logs: `docker-compose logs listener`

### No data appearing on map

- Verify listener is connected: Check logs
- Ensure repeaters are broadcasting advertisements
- Check API keys are configured correctly
- Verify Processing service is running: `curl http://localhost:8000/health`

### Database connection errors

- Ensure PostgreSQL is healthy: `docker-compose ps postgres`
- Check database password in `.env`
- Verify `DATABASE_URL` format

### Traces not executing

- Check trace throttle settings
- Verify listener can reach repeaters
- Review trace schedule: `GET /api/v1/admin/trace-schedule`
- Check trace handler logs

## License

[Your License Here]

## Contributing

Contributions welcome! Please submit pull requests or open issues.

## Support

For MeshCore-related questions, see:
- [MeshCore GitHub](https://github.com/meshcore-dev/meshcore_py)
- [MeshCore Documentation](https://meshcore.co.uk/)

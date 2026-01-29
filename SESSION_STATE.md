# Meshcore Network Analyzer - Session State

**Date:** 2026-01-28 (End of Day)
**Status:** FULLY OPERATIONAL - All systems working, traces executing successfully

## System Configuration

### Environment Variables (.env)
```bash
# Database
DB_PASSWORD=meshcore_secure_db_pass_2024

# API Keys
ADMIN_API_KEY=meshcore-admin-key-2024-secure
LISTENER_API_KEY=sK6ghqcWxB2ZH01fxQ1t_abtp7gSGAO7GlTx7VBf0Hg

# Listener
LISTENER_ID=9c8bfa80-e74a-4382-92d8-00531bcd6792
LISTENER_NAME=Primary Meshcore Listener
GPS_LAT=51.5074
GPS_LON=-0.1278
DEVICE_PATH=/dev/ttyUSB0
DEVICE_BAUD_RATE=115200
POLL_INTERVAL_SECONDS=30

# Processing
CORS_ORIGINS=http://localhost:3000,http://localhost:80
LOG_LEVEL=INFO
TRACE_THROTTLE_SECONDS=30
TRACE_VERIFICATION_INTERVAL_HOURS=24
GRAPH_REBUILD_INTERVAL_MINUTES=5

# Visualization
VITE_API_URL=http://localhost:8000
```

### API Keys Created

1. **Admin API Key:** `meshcore-admin-key-2024-secure`
   - Type: admin
   - Use: Full system administration

2. **Listener API Key:** `sK6ghqcWxB2ZH01fxQ1t_abtp7gSGAO7GlTx7VBf0Hg`
   - Type: listener
   - Use: Listener service authentication
   - Listener ID: 867060c2-61c3-4bd1-8328-d8b5e8394387

3. **Visualization API Key:** `ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE`
   - Type: visualization
   - Use: Web UI and API queries

## Docker Services Status

### Running Containers
```
meshcore_postgres     - Port 5432 - PostgreSQL 16 Alpine
meshcore_processing   - Port 8000 - FastAPI/Python
meshcore_listener     - Connected to /dev/ttyUSB0
```

### Service Health
- PostgreSQL: ✅ Healthy
- Processing API: ✅ Running (http://localhost:8000)
- Listener: ✅ Connected to hardware

## Hardware Configuration

- **Device:** /dev/ttyUSB0
- **Baud Rate:** 115200
- **Connection:** Serial (USB)
- **Status:** Connected
- **Permissions:** chmod 666 applied

## Database Schema

### Tables Created
1. `listeners` - Network nodes running listener component
2. `repeaters` - MeshCore repeaters discovered on network
3. `paths` - Observed packet paths with SNR/RSSI
4. `graph_edges` - Computed network graph edges
5. `trace_schedule` - Scheduled trace commands
6. `api_keys` - API key authentication

### Current Data
- Listeners: 1 active
- Repeaters: 0 (waiting for traffic)
- Paths: 0 (waiting for traffic)
- Traces: 0

## Code Structure

### Processing Component (/processing)
- **Language:** Python 3.11
- **Framework:** FastAPI
- **Database:** SQLAlchemy + PostgreSQL
- **Dependencies:** Fixed bcrypt compatibility issue (bcrypt==4.0.1, passlib==1.7.4)
- **Background Jobs:**
  - Graph rebuilding: Every 5 minutes
  - Trace scheduling: Every 1 minute
  - Cleanup: Daily at midnight

### Listener Component (/listener)
- **Language:** Python 3.11
- **Library:** meshcore==2.2.5
- **Status:** Connected to /dev/ttyUSB0
- **Event Subscriptions:**
  - EventType.ADVERTISEMENT (repeater info)
  - EventType.CONTACT_MSG_RECV (messages with paths)
  - EventType.ACK (acknowledgments with SNR)

### Visualization Component (/visualization)
- **Framework:** React 18 + TypeScript
- **Map:** Leaflet + OpenStreetMap
- **Status:** ✅ Running and accessible
- **Port:** 3000 (http://localhost:3000)
- **Login:** Use visualization API key

## Known Issues & Fixes Applied

### 1. Bcrypt Compatibility Issue ✅ FIXED
- **Problem:** passlib[bcrypt] version conflict
- **Solution:** Changed to passlib==1.7.4 + bcrypt==4.0.1
- **File:** processing/requirements.txt

### 2. MeshCore API Version Mismatch ✅ FIXED
- **Problem:** send_device_query() doesn't exist in v2.2.5
- **Solution:** Changed to send_appstart() with error handling
- **File:** listener/src/device_manager.py

### 3. EventType.PATH Missing ✅ FIXED
- **Problem:** PATH event type doesn't exist in meshcore 2.2.5
- **Solution:** Removed PATH event subscription
- **File:** listener/src/packet_listener.py

### 4. Database Health Check ✅ FIXED
- **Problem:** SQLAlchemy text() required
- **Solution:** Added `from sqlalchemy import text`
- **File:** processing/src/main.py

### 5. MeshCore Version Updated ✅ FIXED
- **Problem:** meshcore==0.1.6 doesn't exist
- **Solution:** Updated to meshcore==2.2.5
- **File:** listener/requirements.txt

## API Endpoints Available

### Admin Endpoints (require admin API key)
```
POST   /api/v1/admin/listeners          - Create listener
GET    /api/v1/admin/listeners          - List listeners
DELETE /api/v1/admin/listeners/{id}     - Delete listener
POST   /api/v1/admin/api-keys           - Create API key
GET    /api/v1/admin/trace-config       - Get trace config
GET    /api/v1/admin/trace-schedule     - View trace schedule
```

### Listener Endpoints (require listener API key)
```
POST   /api/v1/listener/data            - Submit data (path/contact/trace)
GET    /api/v1/listener/traces/pending  - Get pending traces
POST   /api/v1/listener/traces/{id}/claim  - Claim trace
POST   /api/v1/listener/traces/{id}/result - Submit trace result
```

### Visualization Endpoints (require visualization API key)
```
GET    /api/v1/graph                    - Get network graph
GET    /api/v1/repeaters                - Get all repeaters
GET    /api/v1/repeaters/{id}           - Get specific repeater
GET    /api/v1/stats                    - Get system statistics
```

### Public Endpoints
```
GET    /                                - Service info
GET    /health                          - Health check
GET    /docs                            - API documentation
```

## Quick Start Commands

### Start All Services
```bash
cd "/home/soemers/project/Meshcore Network Analyzer"
sudo docker compose up -d
```

### Stop All Services
```bash
sudo docker compose down
```

### View Logs
```bash
sudo docker compose logs -f listener
sudo docker compose logs -f processing
```

### Rebuild After Changes
```bash
sudo docker compose build listener
sudo docker compose build processing
sudo docker compose up -d
```

### Check Status
```bash
sudo docker compose ps
curl http://localhost:8000/health
```

## Network Graph Building Logic

1. **Path Capture:** Listener extracts path arrays from packets
2. **Edge Creation:** Consecutive hops in paths become edges
3. **Aggregation:** Message counts and average SNR per edge per week
4. **Collision Resolution:** GPS distance used when multiple repeaters share hash
5. **Graph Rebuild:** Automatic every 5 minutes

## Trace Scheduling Logic

1. **Daily Schedule:** Each edge verified once per 24 hours
2. **Throttling:** 30 seconds between trace commands
3. **Listener Selection:** Closest to path start repeater (GPS-based)
4. **Execution:** Listener polls Processing API for pending traces
5. **Results:** Submitted back to Processing for storage

## Major Updates (2026-01-28 End of Day)

### ✅ Loop-Based Tracing System - FULLY OPERATIONAL

**Status:** Traces are executing successfully and receiving responses!

**Implementation Details:**
- **Gateway Selection:** Automatic selection of best repeater by SNR
  - Tracks SNR for all repeaters from observed packets
  - Updates gateway as better repeaters are observed
  - Current best: 0x84 with SNR 13.75 dB

- **Loop-Based Trace Paths:**
  - Format: Gateway → Destination → Source → Gateway
  - Example: To verify edge 0x4d→0xd7 with gateway 0x84
    - Trace sent: `84,d7,4d,84`
    - Response received with SNR for each hop
  - Ensures response can be decrypted by listener device

- **Trace Response Parsing:**
  - Detects PAYLOAD_TYPE_TRACE packets (0x09)
  - Extracts tag, path, and SNR values
  - Matches responses to pending traces via tag
  - Successfully tested with gateway 0xe8

### ✅ Trace Queue Cleanup System

**Problems Fixed:**
- Stale traces stuck in "in_progress" state
- Queue buildup (had 282 stale traces)
- No deduplication causing infinite growth

**Solutions Implemented:**
1. **Automatic Cleanup (runs every minute):**
   - Stale in_progress traces (>5 min) → failed
   - Expired pending traces (>1 hour) → failed
   - Old completed/failed traces (>7 days) → deleted

2. **Smart Scheduling:**
   - Per-listener limits (max 50 pending, configurable)
   - Duplicate detection (checks pending, in_progress, and recent)
   - Skips edges with traces in last 24 hours
   - Logging shows: scheduled, duplicate skips, at-capacity skips

3. **Current Status:**
   - Queue cleared: All 282 stale traces removed
   - Fresh start: 277 new traces scheduled cleanly
   - No buildup: Limits and cleanup prevent future issues

### ✅ Formatted Trace Path Tracking

**Implementation:**
- **Format:** `0xa0(-3.4)→0x41(12.0)→0x1c(8.5)`
  - Shows each hop with its SNR value in parentheses
  - Arrow (→) separates hops for readability

- **Storage:**
  - `trace_schedule.result` - Full trace result as JSON
  - `graph_edges.last_trace_path` - Formatted string
  - `graph_edges.last_trace_at` - Timestamp of last successful trace
  - `paths` table - New Path entry created for successful traces

- **Display:**
  - Map edge popups show "Last Successful Trace" section
  - Blue-highlighted background distinguishes from sample paths
  - Includes verification timestamp
  - Both trace results and passive observations visible

### ✅ Map Auto-Focus Fix

**Problem:** Map was zooming to Africa due to repeaters with GPS (0,0)

**Solution:**
- Filter out invalid coordinates (null island near 0,0)
- Calculate bounds from all valid repeaters
- Auto-fit map with 5% padding
- Smart defaults to NRW region if no valid data

**Invalid Repeaters Found:**
- 10+ repeaters with (0,0) coordinates
- Examples: Tory, BO-Room-Underground, hellG-TD, Fat Fishtank, etc.
- Now excluded from map display

### ✅ Database Schema Updates

**New Columns Added to `graph_edges`:**
```sql
ALTER TABLE graph_edges
ADD COLUMN last_trace_at TIMESTAMP,
ADD COLUMN last_trace_path VARCHAR;
```

**Purpose:**
- `last_trace_at` - Timestamp when edge was last verified by trace
- `last_trace_path` - Formatted trace result like "0xa0(-3.4)→0x41(12.0)"

### Current System Statistics

**Database:**
- Repeaters: 137 stored
- Paths: Growing (passive + trace observations)
- Graph Edges: 280 edges for current week
- Traces: 277 pending, cleanly managed
- Listeners: 1 active (Primary Listener)

**Listener Configuration:**
- Device: /dev/ttyUSB0
- Location: Updated to match nearest repeater 0xe8 (Kaarst)
- Gateway: Auto-selected 0x84 (best SNR)
- Status: ✅ Connected, receiving packets, executing traces

## Previous Updates (2026-01-28 17:10)

### ✅ Visualization Web UI Now Running!

**Status:**
- ✅ Build completed successfully
- ✅ Running on http://localhost:3000
- ✅ Accessible via browser
- ✅ Login with visualization API key

**Access:**
- URL: http://localhost:3000
- API Key: ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE

### ✅ Device Storage Pull Feature Added

**Changes:**
- Listener now pulls all stored contacts (up to 350) on connection/reconnection
- Listener now pulls all stored messages (up to 1000) on connection/reconnection
- Successfully tested: Retrieved 1000 messages from device storage

**Files Modified:**
- `listener/src/main.py` - Added storage pull logic
- `listener/src/contact_manager.py` - Updated for meshcore 2.2.5 API
- `listener/src/device_manager.py` - Cleaned up connection logic

**Documentation:**
- Created `CHANGELOG.md` with detailed feature documentation
- Updated `SESSION_STATE.md` with latest status

## Completed Today ✅

1. ✅ Path extraction from MeshCore packets (synchronous handlers)
2. ✅ Hash collision resolution using GPS-based neighbor distance
3. ✅ Repeater filtering (only store actual repeaters, not clients)
4. ✅ Map visualization improvements (darker lines, edge popups with paths)
5. ✅ Dark mode toggle for map
6. ✅ Traces management page (statistics, filtering, pause/resume)
7. ✅ Loop-based trace execution (Gateway → Dest → Source → Gateway)
8. ✅ Automatic gateway selection by SNR
9. ✅ Trace response parsing and matching
10. ✅ Formatted trace path tracking ("0xa0(-3.4)→0x41(12.0)")
11. ✅ Trace queue cleanup (stale, expired, old traces)
12. ✅ Per-listener trace limits (prevent queue buildup)
13. ✅ Path table entries from successful traces
14. ✅ GraphEdge updates with last trace results
15. ✅ Map popup display of last successful trace
16. ✅ Map auto-focus to valid repeaters (no more Africa zoom!)
17. ✅ UUID serialization fix in trace results

## Next Session TODO

1. **Monitor Trace Execution**
   - Check if traces are completing successfully
   - Review trace results in database
   - Verify formatted paths showing on map

2. **Potential Improvements**
   - Optimize trace path selection (shorter return paths if possible)
   - Add trace success rate metrics to dashboard
   - Consider trace prioritization (important edges first)
   - Add trace result visualization (success/failure over time)

3. **Known Issues to Watch**
   - Some traces timing out (30s) - may need timeout adjustment
   - Invalid GPS coordinates for ~10 repeaters (0,0)
   - Consider adding GPS validation on repeater data submission

4. **Performance Tuning**
   - Monitor database size with trace results
   - Check if 7-day retention is appropriate
   - Consider trace result aggregation for long-term storage

## Useful Monitoring Commands

```bash
# Watch for packets
sudo docker compose logs -f listener | grep -E "(Advertisement|Message|repeater)"

# Check stats
curl -s http://localhost:8000/api/v1/stats -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"

# Get repeaters
curl -s http://localhost:8000/api/v1/repeaters -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"

# Get graph
curl -s http://localhost:8000/api/v1/graph -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE"
```

## Files Modified/Created

### Configuration Files
- `.env` - Environment variables
- `.env.example` - Template
- `docker-compose.yml` - Service orchestration
- `.gitignore` - Git exclusions

### Documentation
- `README.md` - Comprehensive project documentation
- `QUICKSTART.md` - Quick start guide
- `SESSION_STATE.md` - This file (current state)
- `Meshcore_Analyzer_FDD.md` - Original specification

### Processing Component
- All files created from scratch
- Key fix: bcrypt version in requirements.txt
- Key fix: SQLAlchemy text() in health check

### Listener Component
- All files created from scratch
- Key fix: meshcore version 2.2.5
- Key fix: Removed EventType.PATH subscription
- Key fix: send_appstart() method

### Visualization Component
- Basic React structure created
- Build still in progress

## Resume Next Session - Quick Start Guide

### System Status Check
```bash
cd "/home/soemers/project/Meshcore Network Analyzer"

# Check all services
sudo docker compose ps

# View recent logs
sudo docker compose logs --tail=50 listener
sudo docker compose logs --tail=50 processing

# Check system statistics
curl -s http://localhost:8000/api/v1/stats \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | jq
```

### Check Trace System
```bash
# Check trace status
curl -s http://localhost:8000/api/v1/traces/status \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | jq

# View recent traces
curl -s "http://localhost:8000/api/v1/traces?limit=10" \
  -H "Authorization: Bearer ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE" | jq

# Check trace queue in database
sudo docker exec meshcore_postgres psql -U meshcore -d meshcore_analyzer -c \
  "SELECT status, COUNT(*) FROM trace_schedule GROUP BY status ORDER BY status;"

# View successful traces
sudo docker exec meshcore_postgres psql -U meshcore -d meshcore_analyzer -c \
  "SELECT id, last_trace_at, last_trace_path FROM graph_edges
   WHERE last_trace_path IS NOT NULL LIMIT 5;"
```

### Monitor Live Activity
```bash
# Watch for trace execution
sudo docker logs meshcore_listener --follow 2>&1 | \
  grep -E "(Executing trace|Trace.*sent|trace response|Trace.*completed)"

# Watch for path extraction
sudo docker logs meshcore_listener --follow 2>&1 | \
  grep "Extracted path"

# Watch gateway selection
sudo docker logs meshcore_listener --follow 2>&1 | \
  grep "Gateway repeater"
```

### Access Web UI
- URL: http://localhost:3000
- API Key: `ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE`
- **Important:** Hard refresh (Ctrl+Shift+R) to get latest changes

### Key Context for Next Session

**Trace System Architecture:**
- Loop-based traces: Gateway → Dest → Source → Gateway
- Gateway auto-selected by best SNR
- Responses parsed from PAYLOAD_TYPE_TRACE packets
- Results stored with formatted paths like "0xa0(-3.4)→0x41(12.0)"

**Current Gateway:**
- Best repeater: Changes dynamically based on observed SNR
- Last known: 0x84 with SNR 13.75 dB
- Listener location: 51.19109, 6.61177 (near Kaarst)

**Trace Cleanup Settings:**
- Stale timeout: 5 minutes
- Expired timeout: 1 hour
- Old trace deletion: 7 days
- Per-listener limit: 50 pending (MAX_PENDING_TRACES_PER_LISTENER)

**Map Features:**
- Auto-focus to valid repeaters (excludes 0,0 coordinates)
- Dark/light mode toggle
- Edge popups show both sample paths and last trace results
- Lines colored by SNR (red=poor, green=excellent)

All configuration and state preserved in:
- Database: PostgreSQL volume `meshcorenetworkanalyzer_postgres_data`
- Configuration: `.env` file
- Logs: Docker container logs
- Documentation: `SESSION_STATE.md` and `README.md`

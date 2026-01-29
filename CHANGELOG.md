# Meshcore Network Analyzer - Changelog

## [Latest] - 2026-01-29

### Fixed: Critical Bug Fixes

**Bug Fixes:**

1. **Graph Edge Message Count Always Zero**
   - **Problem:** Edge message counts always showed 0 despite paths existing
   - **Root Cause:** Only counted paths with trace SNR, not all paths using the edge
   - **Fix:** Separated message counting from SNR tracking in `graph_builder.py`
   - **Result:** All 453 edges now show proper counts (1-125 messages)

2. **Docker Build Failure**
   - **Problem:** GitHub Actions workflow failed when building visualization container
   - **Root Cause:** Lowercase `as` in multi-stage Dockerfile (should be uppercase `AS`)
   - **Fix:** Changed `FROM node:20-alpine as build` to `FROM node:20-alpine AS build`
   - **File:** `visualization/Dockerfile:2`

3. **Trace Paths Missing Routing**
   - **Problem:** Traces used simple 3-hop loops that couldn't work (nodes can't reach each other directly without flooding)
   - **Solution:** Implemented path-based trace generation in `trace_scheduler.py`
   - **Features:**
     - Extracts viable paths from captured network traffic
     - Builds full routing loops: Gateway → Path to From → From → To → Path back → Gateway
     - Uses JSONB containment queries for efficient path searching
     - Includes fallback logic for simple cases
   - **Example:** Instead of `0xe8 → 0xe9 → 0xf5 → 0xe8`, now generates proper routes like `0xe8 → 0x1a → 0x94 → 0xe9 → 0xf5 → 0x94 → 0x1a → 0xe8`

4. **Map Auto-Zoom on Every Update**
   - **Problem:** Map re-centered and zoomed every 30 seconds on data refresh
   - **Fix:** Added `hasSetInitialBounds` state to `MapBoundsHandler` component
   - **Result:** Auto-zoom only happens on initial load, user can freely navigate
   - **File:** `visualization/src/pages/MapView.tsx:11-22`

5. **GPS Coordinates Overwritten with (0, 0)**
   - **Problem:** Valid GPS coordinates replaced when listener sent data without GPS
   - **Fix:** Only update GPS if new coordinates are not (0, 0) or existing are also (0, 0)
   - **File:** `processing/src/api/listeners.py:107-115`

6. **Hash Collision Handling**
   - **Problem:** Different repeaters with same hash would overwrite each other
   - **Root Cause:** Repeater lookup only used hash, not public key
   - **Fix:**
     - First check by public key (true unique identifier)
     - Then check by hash with collision detection
     - Create separate entries when hash matches but public key differs
   - **Impact:** Prevents data loss when two repeaters share the same hash
   - **File:** `processing/src/api/listeners.py:98-119`

7. **Duplicate Listener Creation on Restart**
   - **Problem:** New listener created every time container restarted
   - **Root Cause:** Bcrypt generates different hash each time for same input
   - **Fix:** Check for existing listener by name instead of API key hash
   - **File:** `processing/init_db.py:143-151`

**Database Changes:**
- SNR values cleared and marked with source tracking (`snr_source` column)
- Only trace results populate SNR now, not reception quality
- Trace schedule includes `calculated_path` field for full routing

---

## 2026-01-28 17:10

### Added: Visualization Web UI Deployed ✅

**Status:** Visualization is now live and accessible!

- ✅ Built React + TypeScript application
- ✅ Deployed with nginx in Docker container
- ✅ Running on http://localhost:3000
- ✅ Fixed TypeScript build errors (import.meta.env)

**Access:**
- URL: http://localhost:3000
- Login with API key: `ElJ4xjOMI7TlQPIj5Yqvgvef23gTAXaQEuW7XGN_TSE`

**Features:**
- Interactive OpenStreetMap with repeater markers
- Path visualization with SNR-based coloring
- Admin dashboard with system statistics
- Auto-refresh every 30 seconds
- Responsive design

**Documentation:**
- Created `VISUALIZATION_ACCESS.md` with access instructions
- Updated `SESSION_STATE.md` with current status

---

## 2026-01-28 17:07

### Added: Device Storage Pull on (Re)Connect

**Feature:** Listener now pulls all stored contacts and messages from MeshCore device on connection and reconnection.

#### What Was Changed

**Files Modified:**

1. **`listener/src/main.py`**
   - Added stored contacts pull after connection
   - Added stored messages pull (up to 1000 messages) after connection
   - Added same pull logic on reconnection in health check
   - Messages are pulled from device storage and processed through event handlers

2. **`listener/src/contact_manager.py`**
   - Updated `fetch_contacts()` to use `commands.get_contacts()` for meshcore 2.2.5+
   - Added proper error handling for newer API

3. **`listener/src/device_manager.py`**
   - Cleaned up connection logic
   - Added log message indicating readiness to pull stored data
   - Removed duplicate data pulling (now handled in main.py)

#### How It Works

**On Initial Connection:**
1. Connects to MeshCore device at `/dev/ttyUSB0`
2. Registers packet event handlers
3. Starts auto message fetching (for new incoming messages)
4. **NEW:** Pulls all stored contacts from device (up to 350)
5. **NEW:** Pulls all stored messages from device (up to 1000 safety limit)
6. Processes contacts through contact_manager → sends to Processing API
7. Processes messages through event handlers → extracts paths → sends to Processing API

**On Reconnection:**
1. Detects connection loss (checked every 60 seconds)
2. Attempts reconnection with exponential backoff
3. **NEW:** After successful reconnect, pulls all stored contacts again
4. **NEW:** Pulls all stored messages again (up to 1000)
5. Processes all data through the same pipeline

#### Safety Limits

- **Max messages per pull:** 1000 (prevents infinite loops)
- **Max contacts:** 350 (MeshCore device limit)
- **Reconnect attempts:** 10 with exponential backoff

#### Logs to Watch For

```
INFO:__main__:Fetching stored contacts from device...
INFO:src.contact_manager:Fetched X contacts
INFO:__main__:Pulling stored messages from device...
INFO:__main__:Retrieved X stored messages from device
```

After reconnection:
```
WARNING:__main__:Device connection lost, attempting reconnect...
INFO:__main__:Reconnected - pulling stored data from device...
INFO:__main__:Pulled X stored messages after reconnect
```

#### Testing

Current test results (2026-01-28 17:07):
```
✅ Connected to /dev/ttyUSB0
✅ Fetched 0 contacts (device storage empty)
✅ Retrieved 1000 stored messages from device
✅ Listener service started successfully
```

#### API Version Notes

- Using `meshcore==2.2.5`
- Using `commands.get_contacts()` instead of `get_contacts()`
- Using `commands.get_msg()` instead of `get_msg()`
- Messages retrieved one at a time until ERROR or empty payload

---

## Previous Changes

### 2026-01-28 - Initial Implementation

- Created Processing component with FastAPI
- Created Listener component with meshcore_py
- Created Visualization component with React
- Implemented Docker compose orchestration
- Fixed bcrypt compatibility issue
- Fixed SQLAlchemy text() requirement
- Updated meshcore to version 2.2.5
- Removed EventType.PATH subscription (not available in 2.2.5)

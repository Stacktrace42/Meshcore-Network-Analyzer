# Automatic Database Initialization

The Meshcore Network Analyzer now includes automatic database initialization that runs on first startup. This eliminates the need for manual database setup steps.

## What Gets Initialized Automatically

When you start the system for the first time, the following happens automatically:

### 1. **Database Schema Creation**
- All tables are created automatically (repeaters, paths, graph_edges, trace_schedule, listeners, api_keys, system_config)
- No manual migration steps required

### 2. **System Configuration Seeding**
- Initial configuration values are inserted:
  - `trace_throttle_seconds`: 30
  - `trace_verification_interval_hours`: 24
  - `max_pending_traces_per_listener`: 50

### 3. **Admin API Key Creation**
- Admin API key from `ADMIN_API_KEY` environment variable is hashed and stored
- Used for accessing admin endpoints and configuration management

### 4. **Listener Auto-Creation** (Optional)
- If initialization environment variables are set, a listener is automatically created
- Listener API key is registered in the database
- No need to manually call the admin API to create listeners

## Quick Start from Scratch

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and set your values:**
   ```bash
   # Required: Set secure passwords
   DB_PASSWORD=your-secure-database-password
   ADMIN_API_KEY=your-secure-admin-key

   # Generate a secure random key for the listener
   LISTENER_API_KEY=$(openssl rand -base64 32)

   # Set listener auto-initialization (IMPORTANT: must match LISTENER_API_KEY)
   INIT_LISTENER_NAME=My Meshcore Listener
   INIT_LISTENER_LAT=51.5074
   INIT_LISTENER_LON=-0.1278
   INIT_LISTENER_API_KEY=${LISTENER_API_KEY}  # Same as above!

   # Set your actual GPS coordinates
   GPS_LAT=51.5074
   GPS_LON=-0.1278

   # Set your hardware device path
   DEVICE_PATH=/dev/ttyUSB0
   ```

3. **Start the system:**
   ```bash
   docker-compose pull  # For production images
   # OR
   docker-compose -f docker-compose.build.yml up --build  # For local development

   docker-compose up -d
   ```

4. **Check the logs for the auto-generated listener ID:**
   ```bash
   docker-compose logs processing | grep "Listener.*created"
   ```

   You'll see something like:
   ```
   Listener 'My Meshcore Listener' created successfully (ID: f7aca6d1-e097-4185-971b-c9f4b0938d05)
   ```

5. **Update `.env` with the listener ID (if needed):**
   ```bash
   LISTENER_ID=f7aca6d1-e097-4185-971b-c9f4b0938d05
   ```

6. **Recreate the listener container (only if you updated LISTENER_ID):**
   ```bash
   docker-compose up -d listener
   ```

That's it! The system is ready to use.

## How It Works

### Initialization Script (`processing/init_db.py`)

The initialization script runs automatically before the main application starts. It:

1. **Waits for the database** to be available (up to 60 seconds)
2. **Checks if tables exist** - creates them if they don't
3. **Seeds configuration** - only if system_config table is empty
4. **Creates admin key** - only if no admin key exists
5. **Creates listener** - only if initialization env vars are set and listener doesn't exist

### Entry Point (`processing/entrypoint.sh`)

The Docker container runs this script on startup:
```bash
#!/bin/bash
# Run initialization
python init_db.py

# Start the main application
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Idempotent Design

The initialization is **idempotent** - it can be run multiple times safely:
- Won't create duplicate tables
- Won't overwrite existing configuration
- Won't create duplicate API keys
- Won't create duplicate listeners

This means:
- ✅ Safe to restart containers
- ✅ Safe to run after database backup restore
- ✅ Safe to run in CI/CD pipelines

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_PASSWORD` | PostgreSQL database password | `secure_password_123` |
| `ADMIN_API_KEY` | Admin API key for admin endpoints | `admin-key-here` |
| `LISTENER_API_KEY` | API key for listener authentication | `listener-key-here` |

### Optional Auto-Initialization Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INIT_LISTENER_NAME` | Name for auto-created listener | `Primary Listener` |
| `INIT_LISTENER_LAT` | GPS latitude for listener | `51.5074` |
| `INIT_LISTENER_LON` | GPS longitude for listener | `-0.1278` |
| `INIT_LISTENER_API_KEY` | API key for auto-created listener (must match `LISTENER_API_KEY`) | `listener-key-here` |

**Important:** If all four `INIT_LISTENER_*` variables are set, a listener will be automatically created on first startup. If any are missing, auto-creation is skipped and you'll need to create a listener manually via the admin API.

## Manual Listener Creation (Alternative)

If you prefer not to use auto-initialization:

1. Don't set the `INIT_LISTENER_*` environment variables
2. Start the system: `docker-compose up -d`
3. Create a listener via the admin API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/listeners \
     -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My Listener",
       "gps_lat": 51.5074,
       "gps_lon": -0.1278
     }'
   ```
4. Copy the returned `api_key` and `id` to your `.env` file
5. Restart the listener: `docker-compose restart listener`

## Troubleshooting

### "Database initialization failed"

Check the processing container logs:
```bash
docker-compose logs processing
```

Common issues:
- Database not ready yet (script waits up to 60s automatically)
- Wrong `DATABASE_URL` or `DB_PASSWORD`
- PostgreSQL container not healthy

### "Listener API key invalid"

Make sure:
- `INIT_LISTENER_API_KEY` matches `LISTENER_API_KEY` exactly
- Both listener and processing containers are using the same `.env` file
- You recreated the listener container after changing env vars

### Starting Over

To completely reset and test auto-initialization:

```bash
# Stop all services
docker-compose down

# Remove database volume
docker volume rm meshcorenetworkanalyzer_postgres_data

# Start fresh
docker-compose up -d

# Watch initialization
docker-compose logs -f processing
```

## Benefits

- **Zero manual setup** - just configure `.env` and run
- **Reproducible deployments** - same process every time
- **CI/CD friendly** - automated testing and deployment
- **Documented state** - `.env` file is the source of truth
- **Error handling** - clear error messages if something fails

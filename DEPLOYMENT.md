# Deployment Guide

This guide covers production deployment of the Meshcore Network Analyzer.

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Linux server (Ubuntu 20.04+ recommended)
- MeshCore hardware connected via USB
- Domain name (optional, for HTTPS)
- Minimum 2 GB RAM, 20 GB disk space

## Container Registry Authentication

### For Public Images

No authentication needed. Pull directly:
```bash
docker-compose pull
```

### For Private Repository

1. Create GitHub Personal Access Token (PAT):
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Select scopes: `read:packages`
   - Copy the token

2. Login to GitHub Container Registry:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
   ```

3. Pull images:
   ```bash
   docker-compose pull
   ```

## Initial Setup

### 1. Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 2. Clone Repository (Optional)

If you want the docker-compose files locally:
```bash
git clone https://github.com/Stacktrace42/Meshcore-Network-Analyzer.git
cd Meshcore-Network-Analyzer
```

Or create them manually:
```bash
mkdir meshcore-analyzer
cd meshcore-analyzer
# Copy docker-compose.yml from repository
```

### 3. Configure Environment

Create `.env` file:
```bash
# Database
DB_PASSWORD=your_very_secure_database_password_here

# Admin API Key (use a strong random key)
ADMIN_API_KEY=your_secure_admin_api_key_here

# Listener Configuration
LISTENER_API_KEY=your_listener_api_key_here
LISTENER_ID=listener-primary
LISTENER_NAME=Primary Listener
GPS_LAT=51.5074
GPS_LON=-0.1278

# Hardware
DEVICE_PATH=/dev/ttyUSB0
DEVICE_BAUD_RATE=115200

# Optional: Adjust timing
TRACE_THROTTLE_SECONDS=30
TRACE_VERIFICATION_INTERVAL_HOURS=24
GRAPH_REBUILD_INTERVAL_MINUTES=5

# Optional: For multiple origins
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**Security Notes:**
- Generate strong random keys: `openssl rand -hex 32`
- Never commit `.env` to version control
- Restrict file permissions: `chmod 600 .env`

### 4. Verify Hardware Connection

```bash
# Check if device is connected
ls -l /dev/ttyUSB*

# Check permissions
sudo usermod -aG dialout $USER
# Logout and login again for group changes to take effect

# Test device access
cat /dev/ttyUSB0
# Should show output when packets arrive (Ctrl+C to exit)
```

### 5. Deploy

```bash
# Pull latest images
docker-compose pull

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Database Initialization

### Apply Migrations

```bash
# Enter processing container
docker exec -it meshcore_processing bash

# Run migrations
alembic upgrade head

# Exit container
exit
```

### Seed Initial Data (Optional)

Configuration values are created automatically by the migration. To add additional listeners:

1. Access admin dashboard at `http://your-server:3000/admin`
2. Login with `ADMIN_API_KEY`
3. Create new listener and copy the generated API key

## SSL/HTTPS Setup (Recommended)

### Using Nginx Reverse Proxy

1. Install Nginx:
```bash
sudo apt install nginx certbot python3-certbot-nginx
```

2. Create Nginx config:
```nginx
# /etc/nginx/sites-available/meshcore-analyzer
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. Enable site and get SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/meshcore-analyzer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d yourdomain.com
```

4. Update `.env`:
```bash
CORS_ORIGINS=https://yourdomain.com
VITE_API_URL=https://yourdomain.com
```

## Monitoring

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check container status
docker-compose ps

# View resource usage
docker stats
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f processing

# Last 100 lines
docker-compose logs --tail=100 processing
```

### Database Backup

```bash
# Create backup
docker exec meshcore_postgres pg_dump -U meshcore meshcore_analyzer > backup_$(date +%Y%m%d).sql

# Restore backup
cat backup_20260129.sql | docker exec -i meshcore_postgres psql -U meshcore meshcore_analyzer
```

## Updates

### Pulling New Versions

```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose up -d

# Check for new migrations
docker exec -it meshcore_processing bash -c "alembic upgrade head"
```

### Rollback

```bash
# Use specific image version
docker-compose down
# Edit docker-compose.yml to specify version tag
# Example: ghcr.io/stacktrace42/meshcore-analyzer-processing:v1.0.0
docker-compose up -d
```

## Multiple Listeners

To add additional listener nodes:

1. On new server, follow initial setup steps
2. Use `docker-compose.yml` but only run the `listener` service:
```bash
docker-compose up -d listener
```

3. Configure unique values:
```bash
LISTENER_ID=listener-secondary
LISTENER_NAME=Secondary Listener
GPS_LAT=52.5200
GPS_LON=13.4050
DEVICE_PATH=/dev/ttyUSB0
```

4. Create listener via admin dashboard and use the generated API key

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs processing

# Common issues:
# - Database connection: Check DB_PASSWORD matches
# - Port conflict: Check if port 8000/3000 already in use
# - Missing env vars: Verify .env file exists
```

### Database Connection Failed

```bash
# Check postgres is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Verify connection
docker exec -it meshcore_postgres psql -U meshcore -d meshcore_analyzer
```

### Hardware Not Detected

```bash
# Check USB device
lsusb

# Check permissions
ls -l /dev/ttyUSB0

# Add user to dialout group
sudo usermod -aG dialout $USER
# Logout and login again

# Restart listener
docker-compose restart listener
```

### No Data on Map

1. Check listener is capturing packets:
```bash
docker-compose logs listener | grep "packet"
```

2. Verify repeaters have GPS coordinates in database
3. Check graph rebuild is running:
```bash
docker-compose logs processing | grep "graph"
```

### Trace Not Executing

1. Check trace scheduler status via admin dashboard
2. Verify listener is connected and active
3. Check for errors in processing logs:
```bash
docker-compose logs processing | grep "trace"
```

## Performance Tuning

### PostgreSQL

For large datasets, adjust PostgreSQL settings:

```yaml
# docker-compose.yml
postgres:
  command: postgres -c max_connections=200 -c shared_buffers=256MB -c work_mem=4MB
```

### Graph Rebuild Interval

Reduce frequency for large networks:
```bash
GRAPH_REBUILD_INTERVAL_MINUTES=10
```

### Resource Limits

```yaml
# docker-compose.yml
processing:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

## Security Checklist

- [ ] Strong random passwords for DB and API keys
- [ ] HTTPS enabled with valid certificate
- [ ] Firewall configured (allow only 80, 443)
- [ ] Regular backups scheduled
- [ ] Log rotation configured
- [ ] `.env` file permissions set to 600
- [ ] Container images from trusted registry only
- [ ] Regular security updates applied

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Review this guide
3. Open issue: https://github.com/Stacktrace42/Meshcore-Network-Analyzer/issues

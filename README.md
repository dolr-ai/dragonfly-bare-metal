# Dragonfly Bare Metal Deployment

Production-ready Dragonfly (Redis-compatible) deployment with Docker Compose, configured for high performance and automatic eviction.

## Overview

This setup runs Dragonfly behind an Nginx reverse proxy with TLS termination, configured for:
- 50GB memory limit with automatic eviction (cache mode)
- Data persistence with 6-hour snapshots
- Multi-threaded performance (8 threads)
- Monitoring via HTTP metrics endpoint
- Production-grade logging and health checks

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3 with `redis` package (for management tools)
- SSL certificates in `/etc/letsencrypt` (for production TLS)

### Installation

1. **Clone and setup:**
   ```bash
   cd /root/dragonfly-bare-metal
   
   # Create .env file with your password
   echo 'DRAGONFLY_ROOT_PASSWORD=your_secure_password_here' > .env
   
   # Setup Python virtual environment (for tools)
   python3 -m venv venv
   source venv/bin/activate
   pip install redis
   ```

2. **Start services:**
   ```bash
   docker compose up -d
   ```

3. **Verify deployment:**
   ```bash
   # Check container status
   docker ps
   
   # Run diagnostics
   source venv/bin/activate
   export DRAGONFLY_ROOT_PASSWORD="your_password"
   python tools/diagnose.py
   ```

## Configuration

### Dragonfly Settings

Key configuration in `docker-compose.yml`:

```yaml
# Memory Management
--cache_mode=true           # Enable automatic eviction
--maxmemory=50gb           # Memory limit

# Data Persistence
--dir=/data
--dbfilename=dump
--snapshot_cron=0 */6 * * *  # Snapshot every 6 hours

# Performance
--proactor_threads=8       # Multi-core utilization

# Monitoring
--primary_port_http_enabled=true  # Metrics endpoint
```

### Environment Variables

Required in `.env` file:
```bash
DRAGONFLY_ROOT_PASSWORD=your_secure_password_here
```

### Data Storage

- **Volume mount:** `/mnt/HC_Volume_103551069/dragonfly-data`
- **Snapshot file:** `dump.rdb` (created automatically)
- **Backup schedule:** Every 6 hours via cron

## Architecture

```
Client → Nginx (TLS) → Dragonfly
         :443/:6379     :6379
```

### Services

1. **dragonfly** - Main datastore
   - Internal port: 6379
   - Memory: 50GB max
   - Threads: 8 cores
   - Eviction: Enabled (cache mode)

2. **nginx** - TLS termination and reverse proxy
   - External ports: 80, 443, 6379
   - TLS certificates: `/etc/letsencrypt`
   - Config: `nginx.conf`

## Management Tools

The `tools/` directory contains Python scripts for managing Dragonfly:

- **`diagnose.py`** - System diagnostics and health checks
- **`monitor.py`** - Real-time monitoring dashboard
- **`flood_test.py`** - Load testing and eviction verification
- **`cleanup.py`** - Clean up test data

See [`tools/README.md`](tools/README.md) for detailed usage instructions.

### Quick Examples

```bash
# Activate environment
source venv/bin/activate
export DRAGONFLY_ROOT_PASSWORD="your_password"

# Run diagnostics
python tools/diagnose.py

# Monitor in real-time
python tools/monitor.py

# Load test
python tools/flood_test.py
```

## Eviction Behavior

Dragonfly with `cache_mode=true` automatically evicts keys when memory approaches the limit:

- **Trigger:** ~90% of maxmemory (45GB of 50GB)
- **Algorithm:** Internal Dragonfly eviction (similar to LRU)
- **Behavior:** Old/less-used keys removed automatically
- **Result:** No OOM errors, continuous operation

**Note:** Unlike Redis, Dragonfly doesn't use `--maxmemory-policy`. The `cache_mode` flag handles all eviction automatically.

## Monitoring

### Container Logs
```bash
# View Dragonfly logs
docker logs dragonfly -f

# View Nginx logs
docker logs dragonfly-nginx -f
```

### Metrics Endpoint
```bash
# HTTP metrics (requires --primary_port_http_enabled=true)
curl http://localhost:6379/metrics
```

### Health Checks
```bash
# Container health
docker ps --filter name=dragonfly

# Redis ping
docker exec dragonfly redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" ping
```

## Troubleshooting

### OOM Errors Despite Eviction

1. **Check configuration:**
   ```bash
   python tools/diagnose.py
   ```
   Look for: "✓ Cache mode is enabled" or "✓ Configuration looks correct"

2. **Verify eviction is working:**
   ```bash
   python tools/flood_test.py
   ```
   Should see evicted keys count increasing

3. **Common issues:**
   - Missing `--cache_mode=true` flag
   - Invalid flags (e.g., `--maxmemory-policy` doesn't exist in Dragonfly)
   - Container running old configuration

### Connection Issues

```bash
# Check password
docker exec dragonfly redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" ping

# Check network
docker network inspect dragonfly-bare-metal_default

# Check ports
netstat -tlnp | grep 6379
```

### Performance Issues

```bash
# Check memory usage
docker stats dragonfly

# Monitor real-time metrics
python tools/monitor.py

# Check thread utilization
docker exec dragonfly redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" INFO server
```

## Backup & Recovery

### Manual Backup
```bash
# Trigger snapshot
docker exec dragonfly redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" SAVE

# Copy snapshot file
cp /mnt/HC_Volume_103551069/dragonfly-data/dump.rdb /backup/location/
```

### Restore from Backup
```bash
# Stop container
docker compose stop dragonfly

# Replace snapshot file
cp /backup/location/dump.rdb /mnt/HC_Volume_103551069/dragonfly-data/

# Start container
docker compose start dragonfly
```

### Automated Backups
Snapshots occur automatically every 6 hours via the `--snapshot_cron` setting.

## Maintenance

### Restart Services
```bash
docker compose restart dragonfly
docker compose restart nginx
```

### Update Dragonfly
```bash
# Pull latest image
docker compose pull dragonfly

# Restart with new image
docker compose up -d dragonfly
```

### Clean Up Test Data
```bash
source venv/bin/activate
export DRAGONFLY_ROOT_PASSWORD="your_password"
python tools/cleanup.py
```

## Production Checklist

- [ ] Set strong password in `.env` file
- [ ] Verify TLS certificates are valid
- [ ] Check `cache_mode=true` is enabled
- [ ] Test eviction with `flood_test.py`
- [ ] Set up automated backups
- [ ] Configure monitoring/alerting
- [ ] Review and adjust memory limits
- [ ] Test disaster recovery process
- [ ] Document runbook procedures

## File Structure

```
/root/dragonfly-bare-metal/
├── docker-compose.yml      # Main configuration
├── nginx.conf             # Nginx reverse proxy config
├── .env                   # Environment variables (password)
├── requirements.txt       # Python dependencies
├── venv/                  # Python virtual environment
├── tools/                 # Management scripts
│   ├── README.md         # Tools documentation
│   ├── diagnose.py       # System diagnostics
│   ├── monitor.py        # Real-time monitoring
│   ├── flood_test.py     # Load testing
│   └── cleanup.py        # Test data cleanup
└── README.md             # This file
```

## Resources

- **Dragonfly Documentation:** https://www.dragonflydb.io/docs
- **Configuration Flags:** https://www.dragonflydb.io/docs/managing-dragonfly/flags
- **GitHub Repository:** https://github.com/dragonflydb/dragonfly
- **Command Reference:** https://www.dragonflydb.io/docs/category/command-reference

## License

This deployment configuration is provided as-is. Dragonfly itself is licensed under the BSL 1.1 license.

## Support

For issues with:
- **This deployment:** Review logs and run diagnostics
- **Dragonfly itself:** https://github.com/dragonflydb/dragonfly/issues
- **Documentation:** https://www.dragonflydb.io/docs

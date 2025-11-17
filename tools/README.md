# Dragonfly Management Tools

This folder contains utility scripts for managing and monitoring your Dragonfly instance.

## Prerequisites

All scripts require the virtual environment and environment variables:

```bash
# Activate virtual environment
source ../venv/bin/activate

# Set environment variables
export DRAGONFLY_ROOT_PASSWORD="your_password_here"
export REDIS_HOST="feed-impressions.yral.com"  # or localhost
export REDIS_PORT="6379"  # or 6380 for local testing
export USE_TLS="true"  # or "false" for local connections
```

## Available Tools

### 1. `diagnose.py` - System Diagnostics

Comprehensive diagnostic tool that checks Dragonfly configuration, memory usage, eviction statistics, and provides recommendations.

**Usage:**
```bash
python diagnose.py
```

**What it shows:**
- Configuration settings (cache_mode, maxmemory, eviction policy)
- Memory usage and limits
- Eviction and expiration statistics
- Keyspace information
- Server information
- Diagnosis and recommendations

**When to use:**
- After configuration changes
- When troubleshooting memory issues
- To verify eviction is working correctly
- Regular health checks

---

### 2. `monitor.py` - Real-time Monitoring

Live dashboard showing real-time Dragonfly metrics with automatic refresh.

**Usage:**
```bash
python monitor.py
```

**What it shows:**
- Memory usage (current/max/percentage)
- Total keys across all databases
- Evicted and expired keys
- Hit/miss ratio
- Commands per second
- Connected clients
- Updates every 3 seconds

**When to use:**
- During load testing
- Monitoring production traffic
- Observing eviction behavior
- Performance monitoring

**Controls:**
- Press `Ctrl+C` to exit

---

### 3. `flood_test.py` - Load Testing

Fills Dragonfly with test data to verify eviction behavior and test memory limits.

**Usage:**
```bash
python flood_test.py
```

**Configuration:**
- Batch size: 10,000 keys per batch
- Value size: 10 KB per key (~98 MB per batch)
- Test key prefix: `floodtest:` (safe - won't affect production data)

**What it does:**
- Writes batches of test data continuously
- Reports progress every 5 batches
- Shows keys written, memory usage, and write rate
- Stops on OOM error or manual interrupt (Ctrl+C)

**When to use:**
- Testing eviction configuration
- Load testing before production
- Verifying memory limits work correctly
- Capacity planning

**Warning:** Will fill memory quickly - use on test instances or with monitoring.

---

### 4. `cleanup.py` - Test Data Cleanup

Safely removes flood test data while preserving production keys.

**Usage:**
```bash
python cleanup.py
```

**What it does:**
- Scans for keys with `floodtest:` prefix
- Deletes test keys in batches
- Shows progress and counts
- Preserves all other data

**When to use:**
- After flood testing
- Cleaning up test data from production
- Freeing up memory

**Safety:** Only deletes keys starting with `floodtest:` - production data is safe.

---

## Common Workflows

### Initial Setup Verification
```bash
# 1. Check configuration
python diagnose.py

# 2. Monitor in real-time
python monitor.py
```

### Load Testing Workflow
```bash
# Terminal 1: Start monitoring
python monitor.py

# Terminal 2: Run flood test
python flood_test.py

# Terminal 2: Clean up after testing
python cleanup.py
```

### Troubleshooting OOM Issues
```bash
# 1. Run diagnostics
python diagnose.py

# 2. Check if eviction is configured correctly
# Look for: "✓ Cache mode is enabled" or "✓ Configuration looks correct"

# 3. If issues found, update docker-compose.yml and restart
cd ..
docker compose restart dragonfly

# 4. Verify fix
python diagnose.py
```

### Regular Health Checks
```bash
# Quick check
python diagnose.py | grep -A 5 "DIAGNOSIS"

# Detailed monitoring
python monitor.py
```

## Environment Variables

All scripts support these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DRAGONFLY_ROOT_PASSWORD` | Password for authentication | `""` (empty) |
| `REDIS_HOST` | Dragonfly hostname | `feed-impressions.yral.com` |
| `REDIS_PORT` | Dragonfly port | `6379` |
| `USE_TLS` | Enable TLS connection | `true` |

## Tips

1. **Always use the virtual environment** - Scripts depend on the `redis` Python package
2. **Set password** - Most scripts will fail without `DRAGONFLY_ROOT_PASSWORD`
3. **Local testing** - Use `REDIS_HOST=localhost REDIS_PORT=6380 USE_TLS=false` for local container testing
4. **Monitor during tests** - Run `monitor.py` in one terminal while testing in another
5. **Check eviction** - After any configuration change, run `diagnose.py` to verify

## Troubleshooting

### "Connection failed: Authentication required"
```bash
export DRAGONFLY_ROOT_PASSWORD="your_password"
```

### "Connection refused"
- Check if Dragonfly is running: `docker ps | grep dragonfly`
- Verify host/port: Check `REDIS_HOST` and `REDIS_PORT`
- Check TLS setting: Set `USE_TLS=false` for local connections

### Scripts not found
```bash
# Make sure you're in the right directory
cd /root/dragonfly-bare-metal
source venv/bin/activate
cd tools
```

## Support

For issues with:
- **Dragonfly itself**: https://github.com/dragonflydb/dragonfly/issues
- **Documentation**: https://www.dragonflydb.io/docs
- **These scripts**: Check the script source code for inline comments


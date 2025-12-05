# Dragonfly Migration Eviction Test Guide

## Purpose
Test that Dragonfly's LFRU eviction protects recently added data during production migration.

## Test Scenario
1. **5GB OLD data** (prefix: `should_be_evicted_*`) - Should be evicted first
2. **45GB NEW data** (prefix: `keep_this_*`) - Should stay in RAM
3. **Trigger eviction** by adding more data
4. **Verify**: OLD data evicted, NEW data preserved

This ensures that during production migration, recently migrated keys won't be evicted.

---

## Step-by-Step Instructions

### 1. Start Staging Environment

```bash
# Navigate to project directory
cd /root/dragonfly-bare-metal

# Create staging data directory
mkdir -p /tmp/dragonfly-staging-data

# Start staging Dragonfly (port 6380)
docker compose -f docker-compose.staging.yml up -d

# Wait for health check
sleep 10

# Verify it's running
docker ps | grep dragonfly-staging
```

### 2. Run Migration Eviction Test

```bash
# Activate Python environment
source venv/bin/activate

# Set environment variables
export DRAGONFLY_ROOT_PASSWORD="your_password_here"
export REDIS_PORT=6380

# Run the migration test
python tools/test_migration_eviction.py
```

### 3. Test Flow

The script will:

1. **Connect** to staging Dragonfly
2. **Generate 5GB OLD data** (`should_be_evicted_*` keys)
3. **Generate 45GB NEW data** (`keep_this_*` keys)
4. **Access NEW keys** multiple times (mark as recently used)
5. **Trigger eviction** by adding more data beyond 50GB
6. **Verify results**:
   - OLD keys: <50% survival (evicted as expected)
   - NEW keys: >90% survival (protected by LFRU)

### 4. Expected Output

```
✅ TEST PASSED!
   Old data evicted first, new data protected.
   Safe for production migration!
```

---

## Testing Memory Parameters & Snapshot Recovery

After the eviction test, you can test parameter changes and snapshot recovery:

### Step 1: Take Snapshot

```bash
# Trigger manual snapshot
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" SAVE

# Verify snapshot exists
ls -lh /tmp/dragonfly-staging-data/dump.rdb
```

### Step 2: Modify Parameters

Edit `docker-compose.staging.yml` to test different memory limits:

```yaml
# Example: Test with 40GB maxmemory instead of 50GB
- --maxmemory=40gb

deploy:
  resources:
    limits:
      memory: 45gb
    reservations:
      memory: 40gb
```

### Step 3: Restart and Verify Recovery

```bash
# Stop staging
docker compose -f docker-compose.staging.yml stop

# Start with new parameters
docker compose -f docker-compose.staging.yml up -d

# Check logs for snapshot loading
docker logs dragonfly-staging

# Verify new parameters
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" INFO memory | grep maxmemory
```

### Step 4: Verify Data Integrity

```bash
# Run test script again with option to verify data
python tools/test_migration_eviction.py

# Or manually check
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  --scan --pattern "keep_this_*" | head -10
```

---

## Monitoring During Test

### Terminal 1: Watch Docker Stats
```bash
watch -n 1 'docker stats dragonfly-staging --no-stream'
```

### Terminal 2: Watch Memory Usage
```bash
watch -n 2 "docker exec dragonfly-staging redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO memory | grep -E 'used_memory_human|maxmemory_human'"
```

### Terminal 3: Watch Eviction Stats
```bash
watch -n 2 "docker exec dragonfly-staging redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO stats | grep evicted_keys"
```

---

## Cleanup

```bash
# Stop staging container
docker compose -f docker-compose.staging.yml down

# Remove staging data
rm -rf /tmp/dragonfly-staging-data

# Optional: Remove staging compose file
# rm docker-compose.staging.yml
```

---

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs dragonfly-staging

# Check if port 6380 is already in use
netstat -tlnp | grep 6380
```

### Out of Memory errors
```bash
# Check available system RAM
free -h

# Your system needs 55GB+ free RAM for this test
# If not available, reduce test size in test_migration_eviction.py:
#   OLD_DATA_GB = 2
#   NEW_DATA_GB = 8
```

### Connection refused
```bash
# Check container is running
docker ps | grep dragonfly-staging

# Check health status
docker inspect dragonfly-staging | grep -A 5 Health

# Test connection
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" ping
```

---

## Success Criteria

- ✅ Staging environment starts successfully
- ✅ 50GB of test data generates without errors
- ✅ Eviction triggers when adding more data
- ✅ OLD data (<50% survival) evicted first
- ✅ NEW data (>90% survival) protected
- ✅ Snapshot saves successfully
- ✅ Data recovers after parameter changes
- ✅ New parameters applied correctly

---

## Next Steps for Production

Once tests pass:

1. **Schedule maintenance window**
2. **Backup current production snapshot**
3. **Update production docker-compose.yml** with tested parameters
4. **Restart production Dragonfly**
5. **Monitor eviction metrics** for first 24 hours
6. **Verify no critical data loss**

---

## Notes

- Test uses ~50GB RAM - ensure your system has enough free memory
- Test takes 10-30 minutes depending on disk I/O speed
- Staging uses port 6380 to avoid conflicts with production (6379)
- All test keys have identifiable prefixes for easy cleanup





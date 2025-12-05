# Dragonfly Migration Test - Setup Complete ✓

## What Has Been Created

### 1. Staging Environment
- **File**: `docker-compose.staging.yml`
- **Container**: `dragonfly-staging`
- **Port**: 6380 (separate from production 6379)
- **Data**: `/tmp/dragonfly-staging-data`
- **Memory**: 50GB maxmemory, 55GB Docker limit
- **Status**: ✓ Running and healthy

### 2. Migration Eviction Test Script
- **File**: `tools/test_migration_eviction.py`
- **Purpose**: Test that recently added data is protected from eviction
- **Test Flow**:
  1. Add 5GB OLD data (`should_be_evicted_*`)
  2. Add 45GB NEW data (`keep_this_*`)
  3. Access NEW keys to mark as recently used
  4. Add more data to trigger eviction
  5. Verify OLD data evicted, NEW data preserved

### 3. Supporting Files
- **`TEST_GUIDE.md`**: Detailed step-by-step instructions
- **`run_migration_test.sh`**: Automated test runner
- **`tools/test_memory_limits.py`**: General memory testing tool

---

## Current Status

✅ Staging Dragonfly is running on port 6380
✅ Memory configured: 50GB maxmemory
✅ Test scripts created and ready
✅ Connection tested successfully

---

## Next Steps - Run the Test

### Option A: Automated Test (Recommended)

```bash
cd /root/dragonfly-bare-metal
./run_migration_test.sh
```

This will automatically:
- Verify environment
- Run the full migration test
- Show results

### Option B: Manual Test (More Control)

```bash
cd /root/dragonfly-bare-metal
source venv/bin/activate
source .env
export REDIS_PORT=6380

python tools/test_migration_eviction.py
```

Follow the interactive prompts.

---

## What the Test Will Show

### Success Criteria

```
✅ TEST PASSED!
   Old data evicted first, new data protected.
   Safe for production migration!
```

### Expected Results
- **OLD data survival**: <50% (evicted as expected)
- **NEW data survival**: >90% (protected by LFRU)
- **Memory usage**: Stays at ~50GB
- **Eviction count**: Increases when memory full

### Test Duration
- **Small system**: 10-15 minutes
- **Fast system**: 5-10 minutes
- **Depends on**: Disk I/O, CPU, RAM speed

---

## After the Eviction Test

### Test Snapshot & Recovery

```bash
# 1. Take snapshot
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" SAVE

# 2. Verify snapshot
ls -lh /tmp/dragonfly-staging-data/dump.rdb

# 3. Stop container
docker compose -f docker-compose.staging.yml stop

# 4. Modify parameters in docker-compose.staging.yml
#    (e.g., change maxmemory to 40gb)

# 5. Start container
docker compose -f docker-compose.staging.yml start

# 6. Verify data recovered
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  DBSIZE
```

---

## Monitoring Commands

### Watch Memory Usage
```bash
watch -n 2 "docker exec dragonfly-staging redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO memory | grep -E 'used_memory_human|maxmemory'"
```

### Watch Eviction Stats
```bash
watch -n 2 "docker exec dragonfly-staging redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO stats | grep evicted_keys"
```

### Watch Docker Stats
```bash
watch -n 1 'docker stats dragonfly-staging --no-stream'
```

---

## Cleanup After Testing

```bash
# Stop staging container
docker compose -f docker-compose.staging.yml down

# Remove staging data
rm -rf /tmp/dragonfly-staging-data

# Optional: Keep files for future tests
# Optional: Remove staging files
# rm docker-compose.staging.yml run_migration_test.sh TEST_GUIDE.md
```

---

## Test Configuration

### Current Settings
```yaml
Memory:
  maxmemory: 50gb
  Docker limit: 55gb
  cache_mode: true (LFRU eviction)

Data:
  OLD: 5GB (should_be_evicted_*)
  NEW: 45GB (keep_this_*)
  Value size: 100KB per key

Eviction trigger:
  Starts at: ~45GB (90% of maxmemory)
  Hard limit: 50GB
```

### Adjusting Test Size

If you don't have 55GB+ free RAM, edit `tools/test_migration_eviction.py`:

```python
# Smaller test:
OLD_DATA_GB = 2      # Was 5
NEW_DATA_GB = 8      # Was 45
VALUE_SIZE_KB = 100  # Keep same
```

Also adjust `docker-compose.staging.yml`:

```yaml
- --maxmemory=10gb   # Was 50gb
deploy:
  resources:
    limits:
      memory: 11gb   # Was 55gb
```

---

## Production Migration Plan

Once tests pass:

### 1. Preparation
- ✅ Test completed successfully
- ✅ Understand eviction behavior
- ✅ Backup current production snapshot
- ✅ Schedule maintenance window

### 2. Update Production
```bash
# Edit docker-compose.yml with tested parameters
vi docker-compose.yml

# Stop production
docker compose stop dragonfly

# Start with new config
docker compose up -d dragonfly

# Monitor closely
docker logs -f dragonfly
```

### 3. Monitor After Migration
```bash
# Watch for evictions
watch -n 10 "docker exec dragonfly redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO stats | grep evicted_keys"

# Watch memory
watch -n 10 "docker exec dragonfly redis-cli -a '$DRAGONFLY_ROOT_PASSWORD' INFO memory | grep used_memory_human"

# Check for errors
docker logs dragonfly --tail 100
```

### 4. Rollback Plan (If Needed)
```bash
# Stop dragonfly
docker compose stop dragonfly

# Restore old snapshot (if you backed it up)
cp /backup/dump.rdb /mnt/HC_Volume_103551069/dragonfly-data/

# Revert docker-compose.yml
git checkout docker-compose.yml

# Restart
docker compose up -d dragonfly
```

---

## Key Insights

### How LFRU Protects Recent Data
1. **Frequency**: How often is the key accessed?
2. **Recency**: When was it last accessed?
3. **Combined score**: Keys with low frequency AND old age are evicted first

### Your Migration Scenario
- NEW migrated data: High recency (just added)
- OLD data: Low recency (hasn't been accessed)
- Result: OLD data evicted, NEW data protected ✓

### Why This Matters
- During migration, recently imported keys won't be lost
- System naturally keeps "hot" data in RAM
- "Cold" data is evicted to make room
- Snapshots capture everything before eviction

---

## Questions?

See `TEST_GUIDE.md` for detailed instructions and troubleshooting.

**Ready to test?** Run: `./run_migration_test.sh`





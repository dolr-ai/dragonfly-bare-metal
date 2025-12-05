# Test Eviction DURING Migration

## Purpose

Test what happens when you're actively migrating data into Dragonfly that's already near its memory limit.

## Difference from Previous Test

| Test | Scenario | When Eviction Happens |
|------|----------|----------------------|
| **Previous** | Add OLD, add NEW, then overflow | **AFTER** all data is loaded |
| **This Test** | Fill to 95%, then import NEW | **DURING** the import |

## What This Test Does

```
Step 1: Fill memory to 95% with OLD data (47GB)
        └─ System is at eviction threshold

Step 2: Start importing NEW data (10GB)
        └─ Eviction triggers DURING this import
        └─ OLD data is evicted to make room
        └─ NEW data is successfully added

Step 3: Verify results
        └─ OLD data: <70% survival (evicted)
        └─ NEW data: >95% survival (added successfully)
```

## Run the Test

```bash
cd /root/dragonfly-bare-metal
./run_during_migration_test.sh
```

## Expected Output

```
📦 PHASE 1: Fill with 47GB of OLD data
   Progress: 479,000 keys | 47.81GB (95.6%)
   ✓ OLD data loaded!

🚀 PHASE 2: MIGRATE 10GB NEW data
   ⚡ EVICTION STARTED! (at 5,000 keys migrated)
   🔥 EVICTING: 50,000 keys | 48.2GB | Evicted: 15,000
   🔥 EVICTING: 100,000 keys | 48.5GB | Evicted: 28,000
   ✓ Migration complete!

🔍 VERIFICATION
   OLD Data: 35.2% survival (evicted to make room)
   NEW Data: 98.9% survival (successfully migrated)

✅ TEST PASSED!
   Eviction occurred DURING migration
   OLD data was evicted to make room for NEW data
   Safe for production migration!
```

## What This Proves

✅ **You CAN migrate data into a full Dragonfly**  
✅ **Eviction makes room for NEW data automatically**  
✅ **OLD/stale data is evicted DURING the import**  
✅ **NEW data is successfully added (>95% success)**

## Real Production Scenario

This simulates:

```
Your Production System:
├─ Currently at 45GB/50GB (90% full)
├─ You start migrating 10GB of new data
├─ System exceeds 50GB during import
├─ Eviction kicks in automatically
├─ Old data is removed to make space
└─ New data successfully imported!
```

## Test Parameters

```python
OLD_DATA_GB = 47   # Fill to 95% (triggers eviction threshold)
NEW_DATA_GB = 10   # Import this during eviction
VALUE_SIZE_KB = 100
```

**Adjust these** if you want to test different scenarios:

- Smaller test: `OLD_DATA_GB = 9`, `NEW_DATA_GB = 2` (faster)
- Larger test: `OLD_DATA_GB = 48`, `NEW_DATA_GB = 15` (more stress)

## Duration

- **Phase 1** (47GB OLD data): ~8-10 minutes
- **Phase 2** (10GB migration): ~2-3 minutes
- **Total**: ~10-15 minutes

## Monitoring During Test

Watch eviction happen in real-time:

```bash
# Terminal 1: Watch eviction count
watch -n 1 "docker exec dragonfly-staging redis-cli -a '\$DRAGONFLY_ROOT_PASSWORD' INFO stats | grep evicted_keys"

# Terminal 2: Watch memory
watch -n 1 "docker exec dragonfly-staging redis-cli -a '\$DRAGONFLY_ROOT_PASSWORD' INFO memory | grep used_memory_human"
```

## Success Criteria

✅ **Eviction detected during Phase 2** (migration)  
✅ **NEW data >95% successfully imported**  
✅ **OLD data <70% remaining** (evicted to make room)  
✅ **No OOM errors** (eviction kept up)

## Cleanup

The script will offer to clean up after completion, or manually:

```bash
cd /root/dragonfly-bare-metal
source venv/bin/activate
source .env
export REDIS_PORT=6380

docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  --scan --pattern "old_data:*" | \
  xargs -L 1000 docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" DEL
  
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  --scan --pattern "migrated_data:*" | \
  xargs -L 1000 docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" DEL
```

## After Both Tests Pass

You now have proof that:

1. ✅ **After migration**: Recently added data is protected (first test)
2. ✅ **During migration**: New data successfully imports even when full (this test)

**Conclusion**: Your production migration is safe in both scenarios!

---

## Quick Commands

```bash
# Run the during-migration test
./run_during_migration_test.sh

# Check current memory
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" INFO memory | grep used_memory_human

# Check eviction count
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" INFO stats | grep evicted_keys

# View logs
docker logs dragonfly-staging -f
```





# Dragonfly Test Results

## Test Environment Setup - ✅ COMPLETE

**Date**: November 25, 2025
**Environment**: Staging (dragonfly-staging on port 6380)

---

## Tests Completed

### ✅ 1. Staging Environment Setup
- **Status**: PASSED
- **Container**: dragonfly-staging
- **Port**: 6380
- **Data Volume**: /tmp/dragonfly-staging-data
- **Result**: Container running and healthy

### ✅ 2. Memory Configuration Verification
- **Status**: PASSED
- **Configured maxmemory**: 50GB (53,687,091,200 bytes)
- **Docker memory limit**: 55GB
- **Cache mode**: Enabled (eviction policy active)
- **Memory usage**: 22.31MiB / 55GiB (0.04%)
- **Result**: Configuration matches requirements

### ✅ 3. Snapshot Creation
- **Status**: PASSED
- **Method**: Manual SAVE command
- **Snapshot format**: Dragonfly DFS format (dump-*.dfs files)
- **Files created**: 9 files (dump-0000 through dump-0007, plus dump-summary)
- **Test data**: 10 keys successfully saved
- **Result**: Snapshot mechanism working correctly

### ✅ 4. Data Recovery Test
- **Status**: PASSED
- **Test flow**:
  1. Added 10 test keys
  2. Took snapshot (SAVE command)
  3. Stopped container
  4. Restarted container
  5. Verified data recovery
- **Result**: All 10 keys successfully recovered
- **Verification**: DBSIZE returned 10, all test_key_* keys present

### ✅ 5. Parameter Verification After Restart
- **Status**: PASSED
- **maxmemory after restart**: 53,687,091,200 bytes (50GB)
- **Result**: Parameters correctly applied on restart

---

## Test Scripts Created

### 1. Migration Eviction Test
- **File**: `tools/test_migration_eviction.py`
- **Purpose**: Test that recently added data is protected from eviction
- **Test scenario**:
  - 5GB OLD data (should_be_evicted_*)
  - 45GB NEW data (keep_this_*)
  - Trigger eviction
  - Verify OLD data evicted, NEW data stays

### 2. General Memory Test
- **File**: `tools/test_memory_limits.py`
- **Purpose**: General memory testing and monitoring
- **Features**: Data generation, verification, cleanup

### 3. Automated Test Runner
- **File**: `run_migration_test.sh`
- **Purpose**: Automated test execution
- **Features**: Environment validation, test execution, results display

---

## Configuration Files

### docker-compose.staging.yml
```yaml
Memory Configuration:
  - maxmemory: 50gb
  - cache_mode: true
  - Docker limit: 55gb
  - Docker reservation: 50gb

Network:
  - Port: 6380 (external) → 6379 (internal)

Data:
  - Volume: /tmp/dragonfly-staging-data

Performance:
  - proactor_threads: 8
  - primary_port_http_enabled: true
```

---

## Key Findings

### 1. Dragonfly Snapshot Format
- Uses `.dfs` format (Dragonfly Format Snapshot), not `.rdb`
- Multiple files: dump-0000 through dump-0007 + dump-summary
- One file per thread (8 threads = 8 dump files)
- Summary file coordinates the snapshot

### 2. Memory Configuration
- maxmemory correctly set to 50GB
- Docker limit correctly set to 55GB (overhead for Dragonfly process)
- Eviction policy: "eviction" (LFRU algorithm)
- Configuration persists across restarts

### 3. Recovery Behavior
- Snapshot files persist in volume across container restarts
- Data automatically loads on startup
- No data loss when restarting with same parameters
- Recovery is transparent and automatic

---

## Next Steps - Ready to Run

### Migration Eviction Test (Primary Test)

**Purpose**: Verify that recently migrated data won't be evicted

**Command**:
```bash
cd /root/dragonfly-bare-metal
./run_migration_test.sh
```

**What it tests**:
1. Add 5GB OLD data that should be evicted
2. Add 45GB NEW data that should stay
3. Trigger eviction by exceeding memory limit
4. Verify:
   - OLD data: <50% survival (evicted)
   - NEW data: >90% survival (protected)

**Duration**: 10-30 minutes (depends on system I/O)

**Success criteria**:
```
✅ TEST PASSED!
   Old data evicted first, new data protected.
   Safe for production migration!
```

---

## Production Migration Checklist

Once migration test passes:

- [ ] Review test results
- [ ] Understand eviction behavior
- [ ] Backup current production snapshot
- [ ] Schedule maintenance window
- [ ] Update production docker-compose.yml
- [ ] Test in staging first (this environment)
- [ ] Deploy to production
- [ ] Monitor eviction metrics for 24 hours
- [ ] Verify no critical data loss

---

## Monitoring Commands

### Memory Usage
```bash
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  INFO memory | grep -E "used_memory_human|maxmemory_human"
```

### Eviction Stats
```bash
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" \
  INFO stats | grep evicted_keys
```

### Docker Stats
```bash
docker stats dragonfly-staging --no-stream
```

### Container Logs
```bash
docker logs dragonfly-staging -f
```

---

## Cleanup (When Testing Complete)

```bash
# Stop staging container
docker compose -f docker-compose.staging.yml down

# Remove staging data
rm -rf /tmp/dragonfly-staging-data

# Optional: Remove test files
# rm docker-compose.staging.yml
# rm run_migration_test.sh
# rm TEST_GUIDE.md TEST_SUMMARY.md TEST_RESULTS.md
```

---

## Summary

✅ **All infrastructure tests passed**
✅ **Staging environment ready**
✅ **Snapshot/recovery verified**
✅ **Memory configuration correct**
✅ **Ready for migration eviction test**

**Next action**: Run `./run_migration_test.sh` to execute the migration scenario test.

---

## Support Documentation

- `TEST_GUIDE.md` - Step-by-step instructions
- `TEST_SUMMARY.md` - Quick reference
- `docker-compose.staging.yml` - Staging configuration
- `tools/test_migration_eviction.py` - Migration test script
- `tools/test_memory_limits.py` - General test utilities

---

**Test Environment Status**: ✅ READY FOR MIGRATION TEST





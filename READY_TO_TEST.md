# 🚀 Ready to Test!

## Setup Complete ✅

Your Dragonfly migration test environment is ready!

---

## What's Been Verified

✅ **Staging Dragonfly** running on port 6380  
✅ **Memory limits** configured correctly (50GB maxmemory, 55GB Docker limit)  
✅ **Cache mode** enabled (LFRU eviction active)  
✅ **Snapshot mechanism** tested and working  
✅ **Data recovery** verified (stop/start works correctly)  
✅ **Test scripts** created and ready  

---

## Run Your Migration Test Now

This test answers your key question:

> **"During production migration, will recently added keys be evicted?"**

### Quick Start

```bash
cd /root/dragonfly-bare-metal
./run_migration_test.sh
```

### What This Tests

1. **Add 5GB OLD data** (`should_be_evicted_*`)
   - Simulates old/stale data in your system

2. **Add 45GB NEW data** (`keep_this_*`)
   - Simulates recently migrated/imported data

3. **Trigger eviction** by adding more data
   - Forces memory to exceed 50GB limit

4. **Verify results**
   - OLD data should be evicted (<50% survival)
   - NEW data should stay in RAM (>90% survival)

### Expected Outcome

```
✅ TEST PASSED!
   Old data evicted first, new data protected.
   Safe for production migration!
```

This confirms LFRU protects recently added data!

---

## Test Duration

- **Fast system**: 5-10 minutes
- **Normal system**: 10-20 minutes
- **Slow I/O**: 20-30 minutes

Generating 50GB of data takes time. Be patient!

---

## While Test Runs

### Watch Memory (Terminal 1)
```bash
cd /root/dragonfly-bare-metal
source .env
watch -n 2 "docker exec dragonfly-staging redis-cli -a '\$DRAGONFLY_ROOT_PASSWORD' INFO memory | grep used_memory_human"
```

### Watch Eviction (Terminal 2)
```bash
cd /root/dragonfly-bare-metal
source .env
watch -n 2 "docker exec dragonfly-staging redis-cli -a '\$DRAGONFLY_ROOT_PASSWORD' INFO stats | grep evicted_keys"
```

### Watch Docker Stats (Terminal 3)
```bash
watch -n 1 'docker stats dragonfly-staging --no-stream'
```

---

## After Test Completes

### If Test Passes ✅

Your production migration is safe! 

**Next steps**:
1. Review results in test output
2. Plan production migration window
3. Backup production data
4. Apply configuration to production
5. Monitor for 24 hours

### If Test Fails ❌

Review the output to understand:
- Was eviction triggered?
- How much data was evicted?
- Did new data get evicted too early?

Possible solutions:
- Increase memory allocation
- Adjust test data sizes
- Review cache_mode settings

---

## Alternative: Run Test Manually

For more control:

```bash
cd /root/dragonfly-bare-metal
source venv/bin/activate
source .env
export REDIS_PORT=6380

python tools/test_migration_eviction.py
```

This gives you an interactive menu.

---

## Cleanup After Testing

**Don't clean up yet!** Run the test first.

When you're done testing:

```bash
# Stop staging
docker compose -f docker-compose.staging.yml down

# Remove staging data
rm -rf /tmp/dragonfly-staging-data
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `run_migration_test.sh` | **Run this** - Automated test |
| `tools/test_migration_eviction.py` | Migration test script |
| `docker-compose.staging.yml` | Staging environment config |
| `TEST_GUIDE.md` | Detailed instructions |
| `TEST_SUMMARY.md` | Quick reference |
| `TEST_RESULTS.md` | Test verification results |

---

## Current Status

```
Container: dragonfly-staging
Status:    Running ✓
Port:      6380
Memory:    50GB maxmemory / 55GB limit
Mode:      cache_mode=true (eviction enabled)
Data:      /tmp/dragonfly-staging-data
Threads:   8
```

---

## Need Help?

1. Check `TEST_GUIDE.md` for detailed steps
2. Check `TEST_RESULTS.md` for verification tests
3. Check logs: `docker logs dragonfly-staging`

---

## 🎯 Your Goal

Prove that during migration:
- ✅ Recently migrated data **stays in RAM**
- ✅ Old/stale data **gets evicted first**
- ✅ LFRU algorithm **protects new data**

**Ready? Run the test!**

```bash
./run_migration_test.sh
```

Good luck! 🚀





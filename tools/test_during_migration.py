#!/usr/bin/env python3
"""
Test eviction behavior DURING migration.
Fills memory to 95%, then imports new data while eviction is happening.
"""

import redis
import os
import sys
import time

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6380'))
REDIS_PASSWORD = os.getenv('DRAGONFLY_ROOT_PASSWORD')

# Test parameters - smaller for faster testing
OLD_DATA_GB = 47      # Fill to 95% of 50GB (triggers eviction threshold)
NEW_DATA_GB = 10      # Import this DURING eviction
VALUE_SIZE_KB = 100   # 100KB per value

def connect_redis():
    """Connect to Redis/Dragonfly"""
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        r.ping()
        print(f"✓ Connected to Dragonfly at {REDIS_HOST}:{REDIS_PORT}")
        return r
    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Dragonfly: {e}")
        sys.exit(1)

def format_bytes(bytes_value):
    """Format bytes to human readable string"""
    if bytes_value is None:
        return "N/A"
    bytes_value = float(bytes_value)
    if bytes_value < 1024**3:
        return f"{bytes_value / 1024**2:.2f} MB"
    else:
        return f"{bytes_value / 1024**3:.2f} GB"

def get_memory_info(r):
    """Get memory statistics"""
    info = r.info('memory')
    return {
        'used_memory': info.get('used_memory', 0),
        'used_memory_human': info.get('used_memory_human', 'N/A'),
        'maxmemory': info.get('maxmemory', 0),
        'maxmemory_human': info.get('maxmemory_human', 'N/A'),
    }

def get_eviction_stats(r):
    """Get eviction statistics"""
    info = r.info('stats')
    return {
        'evicted_keys': info.get('evicted_keys', 0),
    }

def fill_with_old_data(r, target_gb):
    """Fill memory with OLD data to trigger eviction threshold"""
    print(f"\n{'='*60}")
    print(f"📦 PHASE 1: Fill with {target_gb}GB of OLD data")
    print(f"   Goal: Reach ~95% of memory (eviction threshold)")
    print(f"{'='*60}")
    
    target_bytes = target_gb * 1024**3
    bytes_per_key = VALUE_SIZE_KB * 1024
    estimated_keys = int(target_bytes / bytes_per_key)
    
    value = 'x' * (VALUE_SIZE_KB * 1024)
    batch_size = 1000
    keys_created = 0
    start_time = time.time()
    
    mem_start = get_memory_info(r)
    print(f"   Starting memory: {mem_start['used_memory_human']}")
    print(f"   Target: {target_gb}GB ({estimated_keys:,} keys)")
    print()
    
    while keys_created < estimated_keys:
        pipe = r.pipeline()
        
        for i in range(batch_size):
            key = f"old_data:{keys_created + i}"
            pipe.set(key, value)
        
        pipe.execute()
        keys_created += batch_size
        
        if keys_created % (batch_size * 10) == 0:
            mem = get_memory_info(r)
            used_gb = mem['used_memory'] / (1024**3)
            elapsed = time.time() - start_time
            rate = keys_created / elapsed if elapsed > 0 else 0
            pct = (mem['used_memory'] / mem['maxmemory'] * 100) if mem['maxmemory'] > 0 else 0
            
            print(f"   Progress: {keys_created:,} keys | {used_gb:.2f}GB ({pct:.1f}%) | {rate:.0f} keys/sec")
            
            # Stop when we reach target
            if mem['used_memory'] >= target_bytes * 0.95:
                break
    
    mem_end = get_memory_info(r)
    elapsed = time.time() - start_time
    pct = (mem_end['used_memory'] / mem_end['maxmemory'] * 100) if mem_end['maxmemory'] > 0 else 0
    
    print(f"\n✓ OLD data loaded!")
    print(f"   Keys created: {keys_created:,}")
    print(f"   Memory: {mem_end['used_memory_human']} ({pct:.1f}% of max)")
    print(f"   Time: {elapsed:.1f}s")
    
    return keys_created

def migrate_new_data_during_eviction(r, target_gb):
    """Migrate NEW data while eviction is happening"""
    print(f"\n{'='*60}")
    print(f"🚀 PHASE 2: MIGRATE {target_gb}GB NEW data")
    print(f"   This will trigger eviction DURING migration!")
    print(f"{'='*60}")
    
    target_bytes = target_gb * 1024**3
    bytes_per_key = VALUE_SIZE_KB * 1024
    estimated_keys = int(target_bytes / bytes_per_key)
    
    value = 'y' * (VALUE_SIZE_KB * 1024)
    batch_size = 1000
    keys_created = 0
    start_time = time.time()
    
    mem_start = get_memory_info(r)
    eviction_start = get_eviction_stats(r)
    
    print(f"   Starting memory: {mem_start['used_memory_human']}")
    print(f"   Starting evictions: {eviction_start['evicted_keys']:,}")
    print(f"   Target: {target_gb}GB ({estimated_keys:,} keys)")
    print()
    print(f"   🔄 Starting migration...")
    
    eviction_detected = False
    first_eviction_at = None
    
    try:
        while keys_created < estimated_keys:
            pipe = r.pipeline()
            
            for i in range(batch_size):
                key = f"migrated_data:{keys_created + i}"
                pipe.set(key, value)
            
            pipe.execute()
            keys_created += batch_size
            
            if keys_created % (batch_size * 5) == 0:  # Check more frequently
                mem = get_memory_info(r)
                eviction = get_eviction_stats(r)
                used_gb = mem['used_memory'] / (1024**3)
                elapsed = time.time() - start_time
                rate = keys_created / elapsed if elapsed > 0 else 0
                
                evicted_now = eviction['evicted_keys'] - eviction_start['evicted_keys']
                
                if evicted_now > 0 and not eviction_detected:
                    eviction_detected = True
                    first_eviction_at = keys_created
                    print(f"\n   ⚡ EVICTION STARTED! (at {keys_created:,} keys migrated)")
                    print()
                
                status = "🔥 EVICTING" if evicted_now > 0 else "✓ Migrating"
                print(f"   {status}: {keys_created:,} keys | {used_gb:.2f}GB | "
                      f"Evicted: {evicted_now:,} | {rate:.0f} keys/sec")
    
    except redis.exceptions.ResponseError as e:
        if "OOM" in str(e):
            print(f"\n   ⚠️  Hit OOM - eviction couldn't keep up!")
        else:
            raise
    
    mem_end = get_memory_info(r)
    eviction_end = get_eviction_stats(r)
    elapsed = time.time() - start_time
    
    total_evicted = eviction_end['evicted_keys'] - eviction_start['evicted_keys']
    
    print(f"\n✓ Migration complete!")
    print(f"   Keys migrated: {keys_created:,}")
    print(f"   Memory: {mem_end['used_memory_human']}")
    print(f"   Total evicted DURING migration: {total_evicted:,}")
    if first_eviction_at:
        print(f"   Eviction started after: {first_eviction_at:,} keys migrated")
    print(f"   Time: {elapsed:.1f}s")
    
    return keys_created, total_evicted, eviction_detected

def verify_during_migration(r, old_count, new_count, eviction_happened):
    """Verify that OLD keys were evicted and NEW keys were added"""
    print(f"\n{'='*60}")
    print(f"🔍 VERIFICATION - What survived?")
    print(f"{'='*60}")
    
    # Check OLD keys
    print(f"\n   Checking OLD keys (old_data:*)...")
    old_sample_size = min(1000, old_count)
    old_found = 0
    
    for i in range(0, old_count, max(1, old_count // old_sample_size)):
        key = f"old_data:{i}"
        if r.exists(key):
            old_found += 1
    
    old_survival_rate = (old_found / old_sample_size) * 100
    
    # Check NEW keys (the ones we just migrated)
    print(f"   Checking NEW migrated keys (migrated_data:*)...")
    new_sample_size = min(1000, new_count)
    new_found = 0
    
    for i in range(0, new_count, max(1, new_count // new_sample_size)):
        key = f"migrated_data:{i}"
        if r.exists(key):
            new_found += 1
    
    new_survival_rate = (new_found / new_sample_size) * 100
    
    # Print results
    print(f"\n{'='*60}")
    print(f"📊 RESULTS - DURING MIGRATION TEST")
    print(f"{'='*60}")
    
    print(f"\n   OLD Data (old_data:*):")
    print(f"      Sample checked: {old_sample_size:,} keys")
    print(f"      Found: {old_found:,} keys ({old_survival_rate:.1f}%)")
    
    if old_survival_rate < 70:
        print(f"      ✓ GOOD: OLD data was evicted during migration!")
    else:
        print(f"      ⚠️  Most old data survived (not enough eviction)")
    
    print(f"\n   NEW Migrated Data (migrated_data:*):")
    print(f"      Sample checked: {new_sample_size:,} keys")
    print(f"      Found: {new_found:,} keys ({new_survival_rate:.1f}%)")
    
    if new_survival_rate > 95:
        print(f"      ✓ EXCELLENT: Migrated data successfully added!")
    elif new_survival_rate > 80:
        print(f"      ✓ GOOD: Most migrated data was added")
    else:
        print(f"      ⚠️  WARNING: Too much migrated data was lost!")
    
    # Final verdict
    print(f"\n{'='*60}")
    if eviction_happened and new_survival_rate > 95:
        print(f"✅ TEST PASSED!")
        print(f"   Eviction occurred DURING migration")
        print(f"   OLD data was evicted to make room for NEW data")
        print(f"   {new_survival_rate:.1f}% of migrated data successfully added")
        print(f"   Safe for production migration!")
    elif not eviction_happened:
        print(f"⚠️  TEST INCONCLUSIVE")
        print(f"   No eviction occurred during migration")
        print(f"   Memory might not have been full enough")
        print(f"   Try increasing OLD_DATA_GB in the script")
    else:
        print(f"❌ TEST FAILED")
        print(f"   Too much migrated data was lost during migration")
        print(f"   Review memory configuration")
    print(f"{'='*60}\n")

def cleanup(r):
    """Clean up test data"""
    print(f"\n🧹 Cleaning up test data...")
    
    patterns = ["old_data:*", "migrated_data:*"]
    total_deleted = 0
    
    for pattern in patterns:
        cursor = 0
        deleted = 0
        
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=1000)
            
            if keys:
                pipe = r.pipeline()
                for key in keys:
                    pipe.delete(key)
                pipe.execute()
                deleted += len(keys)
            
            if cursor == 0:
                break
        
        if deleted > 0:
            print(f"   Deleted {deleted:,} keys matching {pattern}")
            total_deleted += deleted
    
    print(f"   ✓ Total deleted: {total_deleted:,} keys")

def main():
    """Main test flow"""
    if not REDIS_PASSWORD:
        print("Error: DRAGONFLY_ROOT_PASSWORD environment variable not set")
        sys.exit(1)
    
    print("=" * 60)
    print("DRAGONFLY EVICTION DURING MIGRATION TEST")
    print("=" * 60)
    print("\nThis test simulates:")
    print("  1. System already at 95% memory (OLD data)")
    print("  2. Start importing NEW data (migration)")
    print("  3. Eviction happens DURING the import")
    print("  4. Verify NEW data is successfully added")
    print("=" * 60)
    
    r = connect_redis()
    
    # Show initial state
    mem = get_memory_info(r)
    eviction = get_eviction_stats(r)
    print(f"\n📊 Initial State:")
    print(f"   Memory: {mem['used_memory_human']} / {mem['maxmemory_human']}")
    print(f"   Evicted keys: {eviction['evicted_keys']:,}")
    
    input("\nPress Enter to start test...")
    
    # Phase 1: Fill with OLD data to 95%
    old_count = fill_with_old_data(r, OLD_DATA_GB)
    
    mem = get_memory_info(r)
    pct = (mem['used_memory'] / mem['maxmemory'] * 100) if mem['maxmemory'] > 0 else 0
    print(f"\n📊 Memory Status Before Migration:")
    print(f"   Used: {mem['used_memory_human']} ({pct:.1f}% of max)")
    
    if pct < 85:
        print(f"   ⚠️  Warning: Memory not full enough. Increase OLD_DATA_GB")
    
    input("\nPress Enter to start migration (will trigger eviction)...")
    
    # Phase 2: Migrate NEW data (eviction will happen DURING this)
    new_count, evicted, eviction_happened = migrate_new_data_during_eviction(r, NEW_DATA_GB)
    
    # Phase 3: Verify results
    verify_during_migration(r, old_count, new_count, eviction_happened)
    
    # Cleanup
    response = input("\nClean up test data? (y/n): ")
    if response.lower() == 'y':
        cleanup(r)
        mem = get_memory_info(r)
        print(f"\n📊 After Cleanup:")
        print(f"   Memory: {mem['used_memory_human']}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()





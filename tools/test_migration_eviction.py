#!/usr/bin/env python3
"""
Test eviction behavior for production migration scenario.
Tests that old data gets evicted before recently added data.
"""

import redis
import os
import sys
import time
import random

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6380'))
REDIS_PASSWORD = os.getenv('DRAGONFLY_ROOT_PASSWORD')

# Test parameters
OLD_DATA_GB = 5      # Old data that should be evicted first
NEW_DATA_GB = 45     # Recent data that should stay (total = 50GB)
VALUE_SIZE_KB = 100  # 100KB per value

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
    elif bytes_value < 1024**4:
        return f"{bytes_value / 1024**3:.2f} GB"
    else:
        return f"{bytes_value / 1024**4:.2f} TB"

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
        'expired_keys': info.get('expired_keys', 0),
    }

def generate_data(r, prefix, target_gb, description):
    """Generate test data with specific prefix"""
    print(f"\n{'='*60}")
    print(f"📝 Generating {target_gb}GB of {description}")
    print(f"   Prefix: {prefix}")
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
    print(f"   Target keys: {estimated_keys:,}")
    print()
    
    while keys_created < estimated_keys:
        pipe = r.pipeline()
        
        for i in range(batch_size):
            key = f"{prefix}{keys_created + i}"
            pipe.set(key, value)
        
        pipe.execute()
        keys_created += batch_size
        
        # Progress update every 10 batches
        if keys_created % (batch_size * 10) == 0:
            mem = get_memory_info(r)
            used_gb = mem['used_memory'] / (1024**3)
            elapsed = time.time() - start_time
            rate = keys_created / elapsed if elapsed > 0 else 0
            
            print(f"   Progress: {keys_created:,} keys | {used_gb:.2f}GB | {rate:.0f} keys/sec")
            
            # Check if we've reached target
            if mem['used_memory'] >= mem_start['used_memory'] + (target_bytes * 0.95):
                break
    
    mem_end = get_memory_info(r)
    elapsed = time.time() - start_time
    
    print(f"\n✓ {description} created!")
    print(f"   Keys created: {keys_created:,}")
    print(f"   Memory now: {mem_end['used_memory_human']}")
    print(f"   Time: {elapsed:.1f}s")
    
    return keys_created

def access_keys(r, prefix, count, access_count=3):
    """Access keys to make them 'recently used' for LFRU"""
    print(f"\n🔄 Accessing {prefix} keys to mark as recently used...")
    
    for _ in range(access_count):
        sample_size = min(1000, count)
        for i in range(0, count, max(1, count // sample_size)):
            key = f"{prefix}{i}"
            r.get(key)
    
    print(f"   ✓ Accessed {prefix} keys {access_count} times")

def trigger_eviction(r):
    """Add more data to trigger eviction"""
    print(f"\n{'='*60}")
    print(f"⚡ TRIGGERING EVICTION - Adding more data...")
    print(f"{'='*60}")
    
    mem_before = get_memory_info(r)
    eviction_before = get_eviction_stats(r)
    
    print(f"   Memory before: {mem_before['used_memory_human']}")
    print(f"   Evicted keys before: {eviction_before['evicted_keys']:,}")
    
    # Try to add 10GB more data
    value = 'z' * (VALUE_SIZE_KB * 1024)
    keys_added = 0
    batch_size = 1000
    
    print(f"\n   Adding new data to push memory limit...")
    
    try:
        for batch in range(100):  # 100 batches
            pipe = r.pipeline()
            
            for i in range(batch_size):
                key = f"trigger_eviction:{keys_added + i}"
                pipe.set(key, value)
            
            pipe.execute()
            keys_added += batch_size
            
            if batch % 10 == 0:
                eviction_now = get_eviction_stats(r)
                mem_now = get_memory_info(r)
                
                print(f"   Batch {batch}: {keys_added:,} keys added | "
                      f"{mem_now['used_memory_human']} | "
                      f"Evicted: {eviction_now['evicted_keys']:,}")
                
                # Stop if eviction started
                if eviction_now['evicted_keys'] > eviction_before['evicted_keys']:
                    print(f"\n   ✓ Eviction triggered!")
                    break
    
    except redis.exceptions.ResponseError as e:
        if "OOM" in str(e):
            print(f"   ⚠️  Hit OOM (Out Of Memory) - memory is full!")
        else:
            raise
    
    mem_after = get_memory_info(r)
    eviction_after = get_eviction_stats(r)
    
    print(f"\n   Memory after: {mem_after['used_memory_human']}")
    print(f"   Evicted keys after: {eviction_after['evicted_keys']:,}")
    print(f"   Total evicted: {eviction_after['evicted_keys'] - eviction_before['evicted_keys']:,}")
    
    return keys_added

def verify_eviction(r, old_prefix, old_count, new_prefix, new_count):
    """Verify that old keys were evicted and new keys remain"""
    print(f"\n{'='*60}")
    print(f"🔍 VERIFICATION - Checking which keys survived")
    print(f"{'='*60}")
    
    # Check OLD keys (should be mostly evicted)
    print(f"\n   Checking OLD keys ({old_prefix}*)...")
    old_sample_size = min(1000, old_count)
    old_found = 0
    old_checked = 0
    
    for i in range(0, old_count, max(1, old_count // old_sample_size)):
        key = f"{old_prefix}{i}"
        if r.exists(key):
            old_found += 1
        old_checked += 1
    
    old_survival_rate = (old_found / old_checked) * 100
    
    # Check NEW keys (should still exist)
    print(f"   Checking NEW keys ({new_prefix}*)...")
    new_sample_size = min(1000, new_count)
    new_found = 0
    new_checked = 0
    
    for i in range(0, new_count, max(1, new_count // new_sample_size)):
        key = f"{new_prefix}{i}"
        if r.exists(key):
            new_found += 1
        new_checked += 1
    
    new_survival_rate = (new_found / new_checked) * 100
    
    # Print results
    print(f"\n{'='*60}")
    print(f"📊 RESULTS")
    print(f"{'='*60}")
    print(f"\n   OLD Data (should_be_evicted_*):")
    print(f"      Checked: {old_checked:,} keys")
    print(f"      Found: {old_found:,} keys ({old_survival_rate:.1f}%)")
    
    if old_survival_rate < 50:
        print(f"      ✓ GOOD: Old data was evicted as expected!")
    else:
        print(f"      ⚠️  WARNING: More old data survived than expected")
    
    print(f"\n   NEW Data (keep_this_*):")
    print(f"      Checked: {new_checked:,} keys")
    print(f"      Found: {new_found:,} keys ({new_survival_rate:.1f}%)")
    
    if new_survival_rate > 90:
        print(f"      ✓ EXCELLENT: New data stayed in RAM!")
    elif new_survival_rate > 75:
        print(f"      ✓ GOOD: Most new data survived")
    else:
        print(f"      ⚠️  WARNING: Too much new data was evicted!")
    
    # Final verdict
    print(f"\n{'='*60}")
    if old_survival_rate < 50 and new_survival_rate > 90:
        print(f"✅ TEST PASSED!")
        print(f"   Old data evicted first, new data protected.")
        print(f"   Safe for production migration!")
    elif new_survival_rate > 75:
        print(f"✅ TEST MOSTLY PASSED")
        print(f"   LFRU is working, but some new data was evicted.")
        print(f"   Consider increasing memory or testing with more load.")
    else:
        print(f"❌ TEST FAILED")
        print(f"   New data is being evicted too aggressively.")
        print(f"   Review configuration before production migration!")
    print(f"{'='*60}\n")

def cleanup(r):
    """Clean up test data"""
    print(f"\n🧹 Cleaning up test data...")
    
    patterns = ["should_be_evicted_*", "keep_this_*", "trigger_eviction:*"]
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
    print("DRAGONFLY MIGRATION EVICTION TEST")
    print("=" * 60)
    print("\nThis test simulates production migration:")
    print("  1. Add 5GB OLD data (should be evicted)")
    print("  2. Add 45GB NEW data (should stay)")
    print("  3. Trigger eviction by adding more data")
    print("  4. Verify OLD data evicted, NEW data stays")
    print("=" * 60)
    
    r = connect_redis()
    
    # Show initial state
    mem = get_memory_info(r)
    eviction = get_eviction_stats(r)
    print(f"\n📊 Initial State:")
    print(f"   Memory: {mem['used_memory_human']} / {mem['maxmemory_human']}")
    print(f"   Evicted keys: {eviction['evicted_keys']:,}")
    
    input("\nPress Enter to start test...")
    
    # Step 1: Generate OLD data (5GB)
    old_count = generate_data(r, "should_be_evicted_", OLD_DATA_GB, "OLD data")
    
    # Step 2: Generate NEW data (45GB)
    time.sleep(2)  # Small delay to ensure timestamp difference
    new_count = generate_data(r, "keep_this_", NEW_DATA_GB, "NEW data")
    
    # Step 3: Access NEW keys to mark as recently used
    access_keys(r, "keep_this_", new_count, access_count=3)
    
    # Show current state
    mem = get_memory_info(r)
    print(f"\n📊 Before Eviction:")
    print(f"   Memory: {mem['used_memory_human']} / {mem['maxmemory_human']}")
    used_pct = (mem['used_memory'] / mem['maxmemory'] * 100) if mem['maxmemory'] > 0 else 0
    print(f"   Usage: {used_pct:.1f}%")
    
    input("\nPress Enter to trigger eviction...")
    
    # Step 4: Trigger eviction
    trigger_eviction(r)
    
    # Step 5: Verify results
    verify_eviction(r, "should_be_evicted_", old_count, "keep_this_", new_count)
    
    # Ask about cleanup
    response = input("\nClean up test data? (y/n): ")
    if response.lower() == 'y':
        cleanup(r)
        mem = get_memory_info(r)
        print(f"\n📊 After Cleanup:")
        print(f"   Memory: {mem['used_memory_human']}")

if __name__ == "__main__":
    main()





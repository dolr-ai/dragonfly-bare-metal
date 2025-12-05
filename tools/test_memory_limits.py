#!/usr/bin/env python3
"""
Test script for Dragonfly memory limits and snapshot recovery.
Generates test data, verifies memory usage, and tests recovery.
"""

import redis
import os
import sys
import time
import random
import string
from datetime import datetime

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6380'))
REDIS_PASSWORD = os.getenv('DRAGONFLY_ROOT_PASSWORD')

# Test parameters
TARGET_MEMORY_GB = 10  # Generate ~10GB of data
VALUE_SIZE_KB = 100  # 100KB per value
BATCH_SIZE = 1000  # Keys per batch
TEST_KEY_PREFIX = "memtest:"

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
    
    if bytes_value < 1024:
        return f"{bytes_value:.2f} B"
    elif bytes_value < 1024**2:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024**3:
        return f"{bytes_value / 1024**2:.2f} MB"
    elif bytes_value < 1024**4:
        return f"{bytes_value / 1024**3:.2f} GB"
    else:
        return f"{bytes_value / 1024**4:.2f} TB"

def get_memory_info(r):
    """Get memory statistics from Dragonfly"""
    info = r.info('memory')
    return {
        'used_memory': info.get('used_memory', 0),
        'used_memory_human': info.get('used_memory_human', 'N/A'),
        'maxmemory': info.get('maxmemory', 0),
        'maxmemory_human': info.get('maxmemory_human', 'N/A'),
        'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
    }

def print_memory_stats(r):
    """Print current memory statistics"""
    mem = get_memory_info(r)
    used = mem['used_memory']
    max_mem = mem['maxmemory']
    
    if max_mem > 0:
        percentage = (used / max_mem) * 100
        print(f"\n📊 Memory Statistics:")
        print(f"   Used: {mem['used_memory_human']} ({percentage:.1f}% of max)")
        print(f"   Max:  {mem['maxmemory_human']}")
        print(f"   Fragmentation: {mem['mem_fragmentation_ratio']:.2f}")
    else:
        print(f"\n📊 Memory Statistics:")
        print(f"   Used: {mem['used_memory_human']}")
        print(f"   Max:  Not set")

def generate_test_data(r, target_gb=10):
    """Generate test data to reach target memory usage"""
    print(f"\n🔄 Generating ~{target_gb}GB of test data...")
    print(f"   Key prefix: {TEST_KEY_PREFIX}")
    print(f"   Value size: {VALUE_SIZE_KB}KB")
    print(f"   Batch size: {BATCH_SIZE} keys")
    
    # Calculate number of keys needed
    target_bytes = target_gb * 1024**3
    bytes_per_key = VALUE_SIZE_KB * 1024
    estimated_keys = int(target_bytes / bytes_per_key)
    
    print(f"   Estimated keys needed: {estimated_keys:,}")
    
    # Generate random data
    value = 'x' * (VALUE_SIZE_KB * 1024)
    
    keys_created = 0
    batch_num = 0
    start_time = time.time()
    
    try:
        while keys_created < estimated_keys:
            batch_num += 1
            pipe = r.pipeline()
            
            for i in range(BATCH_SIZE):
                key = f"{TEST_KEY_PREFIX}{keys_created + i}"
                pipe.set(key, value)
            
            pipe.execute()
            keys_created += BATCH_SIZE
            
            # Progress update every 10 batches
            if batch_num % 10 == 0:
                mem = get_memory_info(r)
                used_gb = mem['used_memory'] / (1024**3)
                elapsed = time.time() - start_time
                rate = keys_created / elapsed if elapsed > 0 else 0
                
                print(f"   Progress: {keys_created:,} keys | {used_gb:.2f}GB used | {rate:.0f} keys/sec")
                
                # Stop if we've reached target
                if mem['used_memory'] >= target_bytes * 0.95:  # 95% of target
                    print(f"   ✓ Reached target memory usage!")
                    break
    
    except redis.exceptions.ResponseError as e:
        if "OOM" in str(e):
            print(f"   ⚠️  Hit memory limit (OOM) - this is expected if testing eviction!")
        else:
            raise
    
    elapsed = time.time() - start_time
    print(f"\n✓ Data generation complete!")
    print(f"   Total keys: {keys_created:,}")
    print(f"   Time taken: {elapsed:.1f}s")
    
    return keys_created

def verify_data(r, expected_keys):
    """Verify that test data exists"""
    print(f"\n🔍 Verifying data integrity...")
    
    # Sample random keys
    sample_size = min(100, expected_keys)
    samples_checked = 0
    samples_found = 0
    
    for i in range(sample_size):
        key_num = random.randint(0, expected_keys - 1)
        key = f"{TEST_KEY_PREFIX}{key_num}"
        
        if r.exists(key):
            samples_found += 1
        samples_checked += 1
    
    success_rate = (samples_found / samples_checked) * 100
    print(f"   Checked {samples_checked} random keys")
    print(f"   Found: {samples_found} ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print(f"   ✓ Data integrity verified!")
        return True
    else:
        print(f"   ⚠️  Data integrity issue - only {success_rate:.1f}% found")
        return False

def trigger_snapshot(r):
    """Trigger a manual snapshot"""
    print(f"\n💾 Triggering manual snapshot...")
    try:
        start_time = time.time()
        r.save()  # Synchronous SAVE command
        elapsed = time.time() - start_time
        print(f"   ✓ Snapshot completed in {elapsed:.1f}s")
        return True
    except Exception as e:
        print(f"   ✗ Snapshot failed: {e}")
        return False

def count_test_keys(r):
    """Count number of test keys"""
    cursor = 0
    count = 0
    
    while True:
        cursor, keys = r.scan(cursor=cursor, match=f"{TEST_KEY_PREFIX}*", count=1000)
        count += len(keys)
        
        if cursor == 0:
            break
    
    return count

def cleanup_test_data(r):
    """Remove all test keys"""
    print(f"\n🧹 Cleaning up test data...")
    
    cursor = 0
    deleted = 0
    
    while True:
        cursor, keys = r.scan(cursor=cursor, match=f"{TEST_KEY_PREFIX}*", count=1000)
        
        if keys:
            pipe = r.pipeline()
            for key in keys:
                pipe.delete(key)
            pipe.execute()
            deleted += len(keys)
            print(f"   Deleted {deleted:,} keys...")
        
        if cursor == 0:
            break
    
    print(f"   ✓ Cleanup complete! Deleted {deleted:,} keys")

def test_eviction(r):
    """Test eviction behavior by filling memory"""
    print(f"\n⚡ Testing eviction behavior...")
    
    mem_before = get_memory_info(r)
    info = r.info('stats')
    evicted_before = info.get('evicted_keys', 0)
    
    print(f"   Memory before: {mem_before['used_memory_human']}")
    print(f"   Evicted keys before: {evicted_before:,}")
    
    # Try to add more data to trigger eviction
    print(f"   Adding more data to trigger eviction...")
    value = 'y' * (VALUE_SIZE_KB * 1024)
    
    try:
        for i in range(10000):
            key = f"{TEST_KEY_PREFIX}eviction:{i}"
            r.set(key, value)
            
            if i % 1000 == 0 and i > 0:
                info = r.info('stats')
                evicted_now = info.get('evicted_keys', 0)
                if evicted_now > evicted_before:
                    print(f"   ✓ Eviction triggered! Keys evicted: {evicted_now:,}")
                    break
    except redis.exceptions.ResponseError as e:
        if "OOM" in str(e):
            print(f"   ⚠️  Hit hard memory limit (OOM)")
        else:
            raise
    
    mem_after = get_memory_info(r)
    info = r.info('stats')
    evicted_after = info.get('evicted_keys', 0)
    
    print(f"   Memory after: {mem_after['used_memory_human']}")
    print(f"   Evicted keys after: {evicted_after:,}")
    
    if evicted_after > evicted_before:
        print(f"   ✓ Eviction is working correctly!")
    else:
        print(f"   ⚠️  No eviction detected - memory might not be full enough")

def main():
    """Main test flow"""
    if not REDIS_PASSWORD:
        print("Error: DRAGONFLY_ROOT_PASSWORD environment variable not set")
        sys.exit(1)
    
    print("=" * 60)
    print("Dragonfly Memory Limits Test")
    print("=" * 60)
    
    r = connect_redis()
    
    # Print initial stats
    print_memory_stats(r)
    
    # Check for existing test data
    existing_keys = count_test_keys(r)
    if existing_keys > 0:
        print(f"\n⚠️  Found {existing_keys:,} existing test keys")
        response = input("   Clean up before continuing? (y/n): ")
        if response.lower() == 'y':
            cleanup_test_data(r)
    
    # Menu
    print("\n" + "=" * 60)
    print("Options:")
    print("  1. Generate test data (~10GB)")
    print("  2. Verify existing data")
    print("  3. Trigger snapshot")
    print("  4. Test eviction")
    print("  5. Print memory stats")
    print("  6. Cleanup test data")
    print("  7. Full test cycle (generate + snapshot + verify)")
    print("  0. Exit")
    print("=" * 60)
    
    choice = input("\nSelect option: ").strip()
    
    if choice == '1':
        keys_created = generate_test_data(r, TARGET_MEMORY_GB)
        print_memory_stats(r)
    elif choice == '2':
        keys = count_test_keys(r)
        if keys > 0:
            verify_data(r, keys)
        else:
            print("   No test keys found")
    elif choice == '3':
        trigger_snapshot(r)
    elif choice == '4':
        test_eviction(r)
    elif choice == '5':
        print_memory_stats(r)
    elif choice == '6':
        cleanup_test_data(r)
        print_memory_stats(r)
    elif choice == '7':
        # Full test cycle
        keys_created = generate_test_data(r, TARGET_MEMORY_GB)
        print_memory_stats(r)
        trigger_snapshot(r)
        verify_data(r, keys_created)
        print("\n✓ Full test cycle complete!")
        print("\nNext steps:")
        print("  1. Stop the container: docker compose -f docker-compose.staging.yml stop")
        print("  2. Modify memory parameters in docker-compose.staging.yml")
        print("  3. Restart: docker compose -f docker-compose.staging.yml start")
        print("  4. Run this script again with option 2 to verify recovery")
    elif choice == '0':
        print("Exiting...")
    else:
        print("Invalid option")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()





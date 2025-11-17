#!/usr/bin/env python3
"""
Cleanup Script for Dragonfly Redis Flood Test
Safely removes only test keys (with floodtest: prefix) while preserving existing data.
"""

import redis
import time
import sys
import os
from datetime import datetime

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'feed-impressions.yral.com')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('DRAGONFLY_ROOT_PASSWORD', '')
USE_TLS = os.getenv('USE_TLS', 'true').lower() == 'true'

# Test configuration
TEST_KEY_PREFIX = "floodtest:"
DELETE_BATCH_SIZE = 1000  # Delete keys in batches

def connect_redis():
    """Connect to Redis/Dragonfly"""
    try:
        if USE_TLS:
            print(f"Connecting to {REDIS_HOST}:{REDIS_PORT} with TLS...")
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                ssl=True,
                ssl_cert_reqs='none',
                decode_responses=True
            )
        else:
            print(f"Connecting to {REDIS_HOST}:{REDIS_PORT} without TLS...")
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
        
        r.ping()
        print("✓ Connected successfully!")
        return r
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

def main():
    print("=" * 70)
    print("Dragonfly Redis Test Data Cleanup")
    print("=" * 70)
    print(f"Target Prefix: {TEST_KEY_PREFIX}*")
    print(f"This will ONLY delete keys starting with '{TEST_KEY_PREFIX}'")
    print(f"All other data will remain untouched.")
    print("=" * 70)
    
    r = connect_redis()
    
    # Count test keys first
    print("\nScanning for test keys...")
    cursor = 0
    test_keys = []
    scan_count = 0
    
    while True:
        cursor, keys = r.scan(cursor, match=f"{TEST_KEY_PREFIX}*", count=1000)
        test_keys.extend(keys)
        scan_count += len(keys)
        
        if scan_count % 10000 == 0 and scan_count > 0:
            print(f"  Found {scan_count:,} test keys so far...")
        
        if cursor == 0:
            break
    
    total_test_keys = len(test_keys)
    
    if total_test_keys == 0:
        print("\n✓ No test keys found. Nothing to clean up!")
        print("=" * 70)
        return
    
    print(f"\nFound {total_test_keys:,} test keys to delete")
    print("\nStarting cleanup...")
    
    # Confirm with user
    response = input(f"\nAre you sure you want to delete {total_test_keys:,} keys? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cleanup cancelled.")
        return
    
    start_time = time.time()
    deleted_count = 0
    
    try:
        # Delete in batches
        for i in range(0, len(test_keys), DELETE_BATCH_SIZE):
            batch = test_keys[i:i + DELETE_BATCH_SIZE]
            
            # Use pipeline for efficient deletion
            pipe = r.pipeline()
            for key in batch:
                pipe.delete(key)
            pipe.execute()
            
            deleted_count += len(batch)
            
            # Progress update
            if deleted_count % 10000 == 0 or deleted_count == total_test_keys:
                elapsed = time.time() - start_time
                percent = (deleted_count / total_test_keys) * 100
                rate = deleted_count / elapsed if elapsed > 0 else 0
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Progress: {deleted_count:,}/{total_test_keys:,} ({percent:.1f}%) | "
                      f"Rate: {rate:,.0f} keys/s")
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("✓ Cleanup completed successfully!")
        print("=" * 70)
        print(f"\nSummary:")
        print(f"  Keys Deleted: {deleted_count:,}")
        print(f"  Time Elapsed: {elapsed:.1f} seconds")
        print(f"  Average Rate: {deleted_count/elapsed:,.0f} keys/s")
        print(f"\n✓ All test data removed. Existing data preserved.")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nCleanup interrupted by user")
        print(f"Deleted {deleted_count:,} out of {total_test_keys:,} keys")
        print("Run the script again to continue cleanup.")
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Flood Test Script for Dragonfly Redis
Fills Redis with test data using a unique prefix to avoid interfering with existing data.
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
BATCH_SIZE = 1000  # Number of keys to write per batch (reduced for near-limit testing)
VALUE_SIZE = 1024 * 10  # 10KB per value (adjust as needed)
REPORT_INTERVAL = 10  # Report progress every N batches

def format_bytes(bytes_value):
    """Format bytes into human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

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
                ssl_cert_reqs='none',  # For self-signed certs
                decode_responses=False
            )
        else:
            print(f"Connecting to {REDIS_HOST}:{REDIS_PORT} without TLS...")
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=False
            )
        
        # Test connection
        r.ping()
        print("✓ Connected successfully!")
        return r
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

def main():
    print("=" * 70)
    print("Dragonfly Redis Flood Test")
    print("=" * 70)
    print(f"Test Key Prefix: {TEST_KEY_PREFIX}")
    print(f"Batch Size: {BATCH_SIZE:,} keys")
    print(f"Value Size: {format_bytes(VALUE_SIZE)} per key")
    print(f"Estimated per batch: {format_bytes(BATCH_SIZE * VALUE_SIZE)}")
    print("=" * 70)
    print("\nPress Ctrl+C to stop at any time\n")
    
    r = connect_redis()
    
    # Generate test value once (reuse for efficiency)
    test_value = b'X' * VALUE_SIZE
    
    total_keys = 0
    total_bytes = 0
    start_time = time.time()
    batch_num = 0
    
    try:
        while True:
            batch_num += 1
            batch_start = time.time()
            
            # Write batch using pipeline for efficiency
            pipe = r.pipeline()
            for i in range(BATCH_SIZE):
                key = f"{TEST_KEY_PREFIX}{total_keys + i}"
                pipe.set(key, test_value)
            
            pipe.execute()
            
            total_keys += BATCH_SIZE
            total_bytes += BATCH_SIZE * VALUE_SIZE
            batch_time = time.time() - batch_start
            
            # Report progress
            if batch_num % REPORT_INTERVAL == 0:
                elapsed = time.time() - start_time
                keys_per_sec = total_keys / elapsed if elapsed > 0 else 0
                mb_per_sec = (total_bytes / elapsed) / (1024 * 1024) if elapsed > 0 else 0
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Batch #{batch_num} | "
                      f"Keys: {total_keys:,} | "
                      f"Data: {format_bytes(total_bytes)} | "
                      f"Rate: {keys_per_sec:,.0f} keys/s ({mb_per_sec:.1f} MB/s) | "
                      f"Batch time: {batch_time:.2f}s")
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("Test stopped by user")
        print("=" * 70)
        elapsed = time.time() - start_time
        print(f"\nSummary:")
        print(f"  Total Keys Written: {total_keys:,}")
        print(f"  Total Data Written: {format_bytes(total_bytes)}")
        print(f"  Time Elapsed: {elapsed:.1f} seconds")
        print(f"  Average Rate: {total_keys/elapsed:,.0f} keys/s")
        print(f"\nTo clean up test data, run: python cleanup.py")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


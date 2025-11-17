#!/usr/bin/env python3
"""
Monitoring Script for Dragonfly Redis
Displays real-time metrics including memory usage, keys, and evictions.
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

# Monitoring configuration
REFRESH_INTERVAL = 3  # Seconds between updates
TEST_KEY_PREFIX = "floodtest:"

def format_bytes(bytes_value):
    """Format bytes into human-readable format"""
    try:
        bytes_value = int(bytes_value)
    except (ValueError, TypeError):
        return "N/A"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def format_number(num):
    """Format number with commas"""
    try:
        return f"{int(num):,}"
    except (ValueError, TypeError):
        return "N/A"

def connect_redis():
    """Connect to Redis/Dragonfly"""
    try:
        if USE_TLS:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                ssl=True,
                ssl_cert_reqs='none',
                decode_responses=True
            )
        else:
            r = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
        
        r.ping()
        return r
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def count_test_keys(r):
    """Count keys with test prefix"""
    try:
        cursor = 0
        count = 0
        # Quick scan with limited iterations for performance
        for _ in range(10):  # Limit scan iterations
            cursor, keys = r.scan(cursor, match=f"{TEST_KEY_PREFIX}*", count=1000)
            count += len(keys)
            if cursor == 0:
                break
        return count if cursor == 0 else f"~{count}+"
    except:
        return "Error"

def main():
    print("Connecting to Dragonfly Redis...")
    r = connect_redis()
    print("✓ Connected! Starting monitor...\n")
    time.sleep(1)
    
    try:
        iteration = 0
        previous_evicted = 0
        
        while True:
            iteration += 1
            
            # Get Redis INFO
            info = r.info()
            stats = info.get('stats', {})
            memory = info.get('memory', {})
            keyspace = info.get('keyspace', {})
            
            # Extract key metrics
            used_memory = memory.get('used_memory', 0)
            used_memory_human = memory.get('used_memory_human', format_bytes(used_memory))
            maxmemory = memory.get('maxmemory', 0)
            maxmemory_human = memory.get('maxmemory_human', format_bytes(maxmemory))
            
            # Calculate memory percentage
            if maxmemory > 0:
                mem_percent = (used_memory / maxmemory) * 100
            else:
                mem_percent = 0
            
            # Get key counts
            db0 = keyspace.get('db0', {})
            if isinstance(db0, dict):
                total_keys = db0.get('keys', 0)
            else:
                # Parse string format "keys=X,expires=Y"
                try:
                    parts = db0.split(',')
                    total_keys = int(parts[0].split('=')[1])
                except:
                    total_keys = 0
            
            # Eviction stats
            evicted_keys = stats.get('evicted_keys', 0)
            keyspace_hits = stats.get('keyspace_hits', 0)
            keyspace_misses = stats.get('keyspace_misses', 0)
            
            # Calculate hit rate
            total_hits_misses = keyspace_hits + keyspace_misses
            if total_hits_misses > 0:
                hit_rate = (keyspace_hits / total_hits_misses) * 100
            else:
                hit_rate = 0
            
            # Eviction rate (keys evicted since last check)
            eviction_rate = evicted_keys - previous_evicted
            previous_evicted = evicted_keys
            
            # Count test keys (only every 5 iterations to reduce overhead)
            if iteration % 5 == 1:
                test_key_count = count_test_keys(r)
            
            # Display dashboard
            clear_screen()
            
            print("=" * 80)
            print("DRAGONFLY REDIS MONITOR".center(80))
            print("=" * 80)
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                  f"Refresh: {REFRESH_INTERVAL}s | "
                  f"Host: {REDIS_HOST}:{REDIS_PORT}")
            print("=" * 80)
            
            # Memory Section
            print("\n📊 MEMORY USAGE")
            print("-" * 80)
            print(f"  Used Memory:      {used_memory_human:>15} / {maxmemory_human}")
            print(f"  Memory Usage:     {mem_percent:>14.2f} %")
            
            # Memory bar
            bar_width = 50
            filled = int(bar_width * min(mem_percent, 100) / 100)
            bar = '█' * filled + '░' * (bar_width - filled)
            print(f"  [{bar}]")
            
            # Keys Section
            print("\n🔑 KEYS")
            print("-" * 80)
            print(f"  Total Keys:       {format_number(total_keys):>15}")
            print(f"  Test Keys:        {str(test_key_count):>15} (prefix: {TEST_KEY_PREFIX})")
            
            # Eviction Section
            print("\n🗑️  EVICTIONS (Spillover/Cache Cleanup)")
            print("-" * 80)
            print(f"  Total Evicted:    {format_number(evicted_keys):>15}")
            print(f"  Since Last Check: {format_number(eviction_rate):>15} keys")
            
            if evicted_keys > 0:
                print(f"  ⚠️  EVICTION ACTIVE - Memory limit reached!")
            else:
                print(f"  ✓ No evictions yet - memory available")
            
            # Performance Section
            print("\n⚡ PERFORMANCE")
            print("-" * 80)
            print(f"  Keyspace Hits:    {format_number(keyspace_hits):>15}")
            print(f"  Keyspace Misses:  {format_number(keyspace_misses):>15}")
            print(f"  Hit Rate:         {hit_rate:>14.2f} %")
            
            # Status Section
            print("\n" + "=" * 80)
            if mem_percent < 80:
                status = "🟢 NORMAL - Memory available"
            elif mem_percent < 95:
                status = "🟡 WARNING - Memory filling up"
            else:
                status = "🔴 CRITICAL - Memory limit reached, evictions active"
            print(f"Status: {status}")
            print("=" * 80)
            print("\nPress Ctrl+C to stop monitoring")
            
            time.sleep(REFRESH_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("Monitor stopped by user")
        print("=" * 80)
    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()


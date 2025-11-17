#!/usr/bin/env python3
"""
Comprehensive Diagnostic Script
Definitively determine why OOM occurs instead of eviction
"""

import redis
import os
import sys

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'feed-impressions.yral.com')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('DRAGONFLY_ROOT_PASSWORD', '')
USE_TLS = os.getenv('USE_TLS', 'true').lower() == 'true'

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

def format_bytes(bytes_value):
    """Format bytes into human-readable format"""
    try:
        bytes_value = int(bytes_value)
    except:
        return str(bytes_value)
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def main():
    print("=" * 80)
    print("DRAGONFLY DIAGNOSTIC REPORT")
    print("=" * 80)
    print()
    
    r = connect_redis()
    
    # Get all server info
    full_info = r.info('all')
    
    print("🔍 CONFIGURATION")
    print("-" * 80)
    
    # Check configuration
    try:
        config = r.config_get()
        
        # Key settings
        maxmemory = config.get('maxmemory', 'Not set')
        maxmemory_policy = config.get('maxmemory-policy', 'Not set')
        
        print(f"maxmemory:          {maxmemory}")
        if maxmemory != 'Not set' and str(maxmemory) != '0':
            print(f"                    ({format_bytes(int(maxmemory))})")
        print(f"maxmemory-policy:   {maxmemory_policy}")
        print()
        
        # Other relevant config
        for key in ['cache_mode', 'save', 'appendonly', 'activedefrag']:
            if key in config:
                print(f"{key:20s}: {config[key]}")
        
    except Exception as e:
        print(f"⚠️  Could not read config: {e}")
    
    print()
    print("📊 MEMORY DETAILS")
    print("-" * 80)
    
    memory = full_info.get('memory', full_info)
    
    # Critical memory stats
    stats_to_show = [
        ('used_memory', 'Used Memory'),
        ('used_memory_human', 'Used Memory (Human)'),
        ('used_memory_rss', 'RSS Memory'),
        ('used_memory_rss_human', 'RSS Memory (Human)'),
        ('used_memory_peak', 'Peak Memory'),
        ('used_memory_peak_human', 'Peak Memory (Human)'),
        ('maxmemory', 'Max Memory Limit'),
        ('maxmemory_human', 'Max Memory (Human)'),
        ('used_memory_dataset', 'Dataset Memory'),
        ('used_memory_overhead', 'Overhead Memory'),
        ('mem_fragmentation_ratio', 'Fragmentation Ratio'),
        ('mem_fragmentation_bytes', 'Fragmentation Bytes'),
    ]
    
    for key, label in stats_to_show:
        if key in memory:
            value = memory[key]
            print(f"{label:25s}: {value}")
    
    print()
    print("🗑️  EVICTION STATISTICS")
    print("-" * 80)
    
    stats = full_info.get('stats', full_info)
    
    eviction_stats = [
        ('evicted_keys', 'Total Evicted Keys'),
        ('expired_keys', 'Total Expired Keys'),
        ('keyspace_hits', 'Keyspace Hits'),
        ('keyspace_misses', 'Keyspace Misses'),
        ('rejected_connections', 'Rejected Connections'),
    ]
    
    for key, label in eviction_stats:
        if key in stats:
            value = stats[key]
            print(f"{label:25s}: {value:,}" if isinstance(value, int) else f"{label:25s}: {value}")
    
    print()
    print("🔑 KEYSPACE INFO")
    print("-" * 80)
    
    keyspace = full_info.get('keyspace', {})
    total_keys = 0
    
    for db, info in keyspace.items():
        if isinstance(info, dict):
            keys = info.get('keys', 0)
            expires = info.get('expires', 0)
        else:
            # Parse string format "keys=X,expires=Y"
            try:
                parts = str(info).split(',')
                keys = int(parts[0].split('=')[1])
                expires = int(parts[1].split('=')[1]) if len(parts) > 1 else 0
            except:
                continue
        
        total_keys += keys
        print(f"{db:10s}: {keys:,} keys, {expires:,} with expiration")
    
    print(f"{'TOTAL':10s}: {total_keys:,} keys")
    
    print()
    print("⚙️  SERVER INFO")
    print("-" * 80)
    
    server = full_info.get('server', full_info)
    
    server_info = [
        ('redis_version', 'Version'),
        ('redis_mode', 'Mode'),
        ('os', 'OS'),
        ('arch_bits', 'Architecture'),
        ('multiplexing_api', 'Event Loop'),
        ('uptime_in_seconds', 'Uptime (seconds)'),
    ]
    
    for key, label in server_info:
        if key in server:
            print(f"{label:20s}: {server[key]}")
    
    print()
    print("=" * 80)
    print("🎯 DIAGNOSIS")
    print("=" * 80)
    print()
    
    # Analyze the situation
    used_mem = memory.get('used_memory', 0)
    max_mem = memory.get('maxmemory', 0)
    evicted = stats.get('evicted_keys', 0)
    # Dragonfly reports eviction policy differently
    policy = memory.get('maxmemory_policy', config.get('maxmemory-policy', 'unknown'))
    cache_mode = memory.get('cache_mode', 'unknown')
    
    try:
        used_mem = int(used_mem)
        max_mem = int(max_mem)
        
        if max_mem == 0:
            print("❌ PROBLEM: maxmemory is set to 0 or unlimited")
            print("   → This means no eviction will occur")
            print("   → Memory will grow until system OOM")
            print()
            
        elif policy == 'noeviction':
            print("❌ PROBLEM: maxmemory-policy is 'noeviction'")
            print("   → When memory is full, all writes are rejected with OOM")
            print("   → No automatic cleanup happens")
            print()
            
        elif policy == 'Not set' or policy == 'unknown':
            # Check if cache_mode is enabled (Dragonfly specific)
            if cache_mode == 'cache':
                print("✓ Cache mode is enabled (Dragonfly eviction active)")
                print(f"   → Policy: {policy}")
                print("   → Eviction will occur when memory limit is reached")
                print()
            else:
                print("⚠️  WARNING: maxmemory-policy is not configured")
                print("   → Default behavior may be 'noeviction'")
                print()
            
        else:
            usage_pct = (used_mem / max_mem * 100) if max_mem > 0 else 0
            
            if evicted == 0 and usage_pct > 80:
                print("⚠️  ISSUE: High memory usage but zero evictions")
                print(f"   → Memory usage: {usage_pct:.1f}%")
                print(f"   → Policy: {policy}")
                print("   → Possible causes:")
                print("      • All keys may be marked as non-evictable")
                print("      • Policy doesn't match key types (e.g., volatile-* with no TTL keys)")
                print("      • Cache mode may not be working correctly")
                print()
            else:
                print(f"✓ Configuration looks correct:")
                print(f"   → Policy: {policy}")
                print(f"   → Memory: {usage_pct:.1f}% used")
                if evicted > 0:
                    print(f"   → Evictions working: {evicted:,} keys evicted")
                print()
        
        # Memory fragmentation check
        frag_ratio = memory.get('mem_fragmentation_ratio', 1.0)
        try:
            frag_ratio = float(frag_ratio)
            if frag_ratio > 1.5:
                print("⚠️  WARNING: High memory fragmentation")
                print(f"   → Fragmentation ratio: {frag_ratio:.2f}")
                print("   → This may cause OOM before reaching maxmemory limit")
                print()
        except:
            pass
            
    except Exception as e:
        print(f"⚠️  Could not complete analysis: {e}")
    
    print("=" * 80)
    print("📋 RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    if policy == 'noeviction' or policy == 'Not set':
        print("1. Change eviction policy:")
        print("   redis-cli CONFIG SET maxmemory-policy allkeys-lru")
        print()
        print("2. Or update docker-compose.yml with:")
        print("   - --maxmemory-policy=allkeys-lru")
        print()
        
    if max_mem == 0:
        print("1. Set maxmemory limit:")
        print("   redis-cli CONFIG SET maxmemory 50gb")
        print()
    
    print("3. Verify cache_mode is enabled:")
    print("   Check docker-compose.yml has: --cache_mode=true")
    print()
    
    print("4. Test eviction after configuration:")
    print("   python flood_test.py")
    print()

if __name__ == "__main__":
    main()


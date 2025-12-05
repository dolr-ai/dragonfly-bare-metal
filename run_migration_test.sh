#!/bin/bash
# Automated test runner for migration eviction test

set -e

cd /root/dragonfly-bare-metal

echo "=========================================="
echo "Dragonfly Migration Eviction Test Runner"
echo "=========================================="
echo

# Load environment
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi

source .env

if [ -z "$DRAGONFLY_ROOT_PASSWORD" ]; then
    echo "Error: DRAGONFLY_ROOT_PASSWORD not set in .env"
    exit 1
fi

# Export for Python script
export DRAGONFLY_ROOT_PASSWORD
export REDIS_PORT=6380

# Activate venv
if [ ! -d venv ]; then
    echo "Error: venv directory not found. Run: python3 -m venv venv && source venv/bin/activate && pip install redis"
    exit 1
fi

source venv/bin/activate

# Check if redis package is installed
if ! python -c "import redis" 2>/dev/null; then
    echo "Installing redis package..."
    pip install redis
fi

echo "✓ Environment ready"
echo

# Check container
if ! docker ps | grep -q dragonfly-staging; then
    echo "Error: dragonfly-staging container not running"
    echo "Start it with: docker compose -f docker-compose.staging.yml up -d"
    exit 1
fi

echo "✓ Staging container running"
echo

# Test connection
if docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" ping 2>&1 | grep -q "PONG"; then
    echo "✓ Connection successful"
else
    echo "Error: Cannot connect to staging Dragonfly"
    exit 1
fi

echo

# Show initial stats
echo "📊 Initial Memory Stats:"
docker exec dragonfly-staging redis-cli -a "$DRAGONFLY_ROOT_PASSWORD" INFO memory 2>/dev/null | grep -E "used_memory_human|maxmemory_human"
echo

# Run the test
echo "Starting migration eviction test..."
echo "This will:"
echo "  1. Add 5GB OLD data (should be evicted)"
echo "  2. Add 45GB NEW data (should stay)"
echo "  3. Trigger eviction"
echo "  4. Verify results"
echo
echo "Note: This test will take 10-30 minutes depending on system speed"
echo
echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
sleep 5

python tools/test_migration_eviction.py

echo
echo "=========================================="
echo "Test Complete!"
echo "=========================================="





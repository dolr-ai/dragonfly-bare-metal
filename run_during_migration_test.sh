#!/bin/bash
# Test eviction DURING migration

set -e

cd /root/dragonfly-bare-metal

echo "=========================================="
echo "Dragonfly DURING Migration Test"
echo "=========================================="
echo

# Load environment
source .env
source venv/bin/activate

export DRAGONFLY_ROOT_PASSWORD
export REDIS_PORT=6380

# Check container
if ! docker ps | grep -q dragonfly-staging; then
    echo "Error: dragonfly-staging not running"
    echo "Start it with: docker compose -f docker-compose.staging.yml up -d"
    exit 1
fi

echo "✓ Staging container running"
echo

# Show what this test does
echo "This test simulates:"
echo "  1. System at 95% memory (47GB OLD data)"
echo "  2. Start importing 10GB NEW data"
echo "  3. Eviction happens DURING import"
echo "  4. Verifies NEW data is successfully added"
echo
echo "Duration: ~10-15 minutes"
echo

# Run test
python tools/test_during_migration.py





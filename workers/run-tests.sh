#!/bin/bash
# Run worker integration tests
# Starts the worker, runs tests, then stops the worker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd "$(dirname "$0")"

echo -e "${YELLOW}Starting worker for tests...${NC}"

# Start worker in background
npx wrangler dev --port 8788 &
WORKER_PID=$!

# Wait for worker to be ready
echo "Waiting for worker to start..."
for i in {1..30}; do
    if curl -s http://localhost:8788/health > /dev/null 2>&1; then
        echo -e "${GREEN}Worker is ready${NC}"
        break
    fi
    sleep 1
done

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
source .venv/bin/activate 2>/dev/null || true

if pytest tests/ -v --tb=short; then
    echo -e "${GREEN}All tests passed!${NC}"
    TEST_EXIT=0
else
    echo -e "${RED}Some tests failed${NC}"
    TEST_EXIT=1
fi

# Cleanup
echo -e "${YELLOW}Stopping worker...${NC}"
kill $WORKER_PID 2>/dev/null || true

exit $TEST_EXIT

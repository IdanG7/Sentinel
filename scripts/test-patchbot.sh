#!/bin/bash
set -e

echo "🤖 PatchBot End-to-End Test Script"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Start services
echo -e "${BLUE}Step 2: Starting Sentinel services...${NC}"
docker-compose up -d postgres redis agent-controller failure-ingestion

echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo -e "${BLUE}Step 3: Checking service health...${NC}"

echo "Checking Agent Controller..."
if curl -sf http://localhost:8003/health > /dev/null; then
    echo -e "${GREEN}✓ Agent Controller is healthy${NC}"
else
    echo -e "${RED}✗ Agent Controller is not responding${NC}"
    exit 1
fi

echo "Checking Failure Ingestion..."
if curl -sf http://localhost:8004/health > /dev/null; then
    echo -e "${GREEN}✓ Failure Ingestion is healthy${NC}"
else
    echo -e "${RED}✗ Failure Ingestion is not responding${NC}"
    exit 1
fi

echo ""

# Simulate a CI failure
echo -e "${BLUE}Step 4: Simulating CI/CD failure...${NC}"

# Create test failure payload
FAILURE_PAYLOAD=$(cat <<EOF
{
  "action": "completed",
  "workflow_run": {
    "id": 123456,
    "name": "CI",
    "head_branch": "test/patchbot-lint",
    "head_sha": "abc123def456",
    "html_url": "https://github.com/test/sentinel/actions/runs/123456",
    "conclusion": "failure",
    "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "run_number": 42
  },
  "repository": {
    "full_name": "test/sentinel",
    "clone_url": "https://github.com/test/sentinel.git"
  }
}
EOF
)

# Send webhook
echo "Sending GitHub webhook to Failure Ingestion..."
RESPONSE=$(curl -s -X POST http://localhost:8004/webhooks/github/workflow_run \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -d "$FAILURE_PAYLOAD")

echo "Response: $RESPONSE"

TASK_ID=$(echo "$RESPONSE" | grep -o '"task_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$TASK_ID" ]; then
    echo -e "${RED}✗ Failed to create task${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Task created: $TASK_ID${NC}"
echo ""

# Check task status
echo -e "${BLUE}Step 5: Monitoring task status...${NC}"
echo "Task ID: $TASK_ID"
echo "Checking task status..."

for i in {1..30}; do
    TASK_STATUS=$(curl -s http://localhost:8003/api/v1/tasks/$TASK_ID | grep -o '"status":"[^"]*' | cut -d'"' -f4)

    echo -e "  Status: ${YELLOW}$TASK_STATUS${NC}"

    if [ "$TASK_STATUS" = "completed" ]; then
        echo -e "${GREEN}✓ Task completed successfully!${NC}"
        break
    elif [ "$TASK_STATUS" = "failed" ]; then
        echo -e "${RED}✗ Task failed${NC}"
        curl -s http://localhost:8003/api/v1/tasks/$TASK_ID | jq .
        exit 1
    fi

    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}⚠ Task still running after 60 seconds${NC}"
        break
    fi

    sleep 2
done

echo ""

# Show task results
echo -e "${BLUE}Step 6: Task Results${NC}"
curl -s http://localhost:8003/api/v1/tasks/$TASK_ID | jq .

echo ""
echo -e "${GREEN}===================================="
echo "🎉 PatchBot Test Complete!"
echo "====================================${NC}"
echo ""
echo "Next steps:"
echo "1. Check the PR created by PatchBot (if configured)"
echo "2. Review the fix in the task results above"
echo "3. View logs: docker-compose logs agent-controller failure-ingestion"
echo ""

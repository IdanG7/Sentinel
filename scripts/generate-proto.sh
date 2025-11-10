#!/bin/bash
# Generate Python gRPC stubs from proto files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$REPO_ROOT/proto"

echo "🔧 Generating Python gRPC stubs..."

# Generate Python stubs for infra-adapter
OUTPUT_DIR="$REPO_ROOT/services/infra-adapter/app/proto"
mkdir -p "$OUTPUT_DIR"

python -m grpc_tools.protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$OUTPUT_DIR" \
  --grpc_python_out="$OUTPUT_DIR" \
  --mypy_out="$OUTPUT_DIR" \
  "$PROTO_DIR/sentinel.proto"

# Fix relative imports in generated files
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  sed -i '' 's/import sentinel_pb2/from . import sentinel_pb2/g' "$OUTPUT_DIR/sentinel_pb2_grpc.py"
else
  # Linux
  sed -i 's/import sentinel_pb2/from . import sentinel_pb2/g' "$OUTPUT_DIR/sentinel_pb2_grpc.py"
fi

# Create __init__.py
cat > "$OUTPUT_DIR/__init__.py" << 'EOF'
"""Generated gRPC code for Sentinel."""

from .sentinel_pb2 import (
    ActionPlan,
    ActionPlanRequest,
    Ack,
    Decision,
    PlanAck,
    Safety,
    TelemetryBatch,
    TelemetryPoint,
    TelemetryRef,
)
from .sentinel_pb2_grpc import (
    DecisionServiceServicer,
    DecisionServiceStub,
    add_DecisionServiceServicer_to_server,
)

__all__ = [
    "ActionPlan",
    "ActionPlanRequest",
    "Ack",
    "Decision",
    "PlanAck",
    "Safety",
    "TelemetryBatch",
    "TelemetryPoint",
    "TelemetryRef",
    "DecisionServiceServicer",
    "DecisionServiceStub",
    "add_DecisionServiceServicer_to_server",
]
EOF

echo "✓ Python stubs generated in $OUTPUT_DIR"

# Generate Go stubs (if protoc-gen-go is available)
if command -v protoc-gen-go &> /dev/null && command -v protoc-gen-go-grpc &> /dev/null; then
    echo "🔧 Generating Go gRPC stubs..."

    GO_OUTPUT_DIR="$REPO_ROOT/services/agent/proto"
    mkdir -p "$GO_OUTPUT_DIR"

    protoc \
      --proto_path="$PROTO_DIR" \
      --go_out="$GO_OUTPUT_DIR" \
      --go_opt=paths=source_relative \
      --go-grpc_out="$GO_OUTPUT_DIR" \
      --go-grpc_opt=paths=source_relative \
      "$PROTO_DIR/sentinel.proto"

    echo "✓ Go stubs generated in $GO_OUTPUT_DIR"
else
    echo "⚠️  Skipping Go stub generation (protoc-gen-go not found)"
fi

echo "✅ All proto generation complete"

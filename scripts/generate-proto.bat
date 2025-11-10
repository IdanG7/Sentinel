@echo off
REM Generate Python gRPC stubs from proto files

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..
set PROTO_DIR=%REPO_ROOT%\proto

echo Generating Python gRPC stubs...

REM Generate Python stubs for infra-adapter
set OUTPUT_DIR=%REPO_ROOT%\services\infra-adapter\app\proto
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

python -m grpc_tools.protoc ^
  --proto_path="%PROTO_DIR%" ^
  --python_out="%OUTPUT_DIR%" ^
  --grpc_python_out="%OUTPUT_DIR%" ^
  --mypy_out="%OUTPUT_DIR%" ^
  "%PROTO_DIR%\sentinel.proto"

if errorlevel 1 (
    echo Error: Failed to generate Python stubs
    exit /b 1
)

REM Fix relative imports in generated files
powershell -Command "(Get-Content '%OUTPUT_DIR%\sentinel_pb2_grpc.py') -replace 'import sentinel_pb2', 'from . import sentinel_pb2' | Set-Content '%OUTPUT_DIR%\sentinel_pb2_grpc.py'"

REM Create __init__.py
(
echo """Generated gRPC code for Sentinel."""
echo.
echo from .sentinel_pb2 import ^(
echo     ActionPlan,
echo     ActionPlanRequest,
echo     Ack,
echo     Decision,
echo     PlanAck,
echo     Safety,
echo     TelemetryBatch,
echo     TelemetryPoint,
echo     TelemetryRef,
echo ^)
echo from .sentinel_pb2_grpc import ^(
echo     DecisionServiceServicer,
echo     DecisionServiceStub,
echo     add_DecisionServiceServicer_to_server,
echo ^)
echo.
echo __all__ = [
echo     "ActionPlan",
echo     "ActionPlanRequest",
echo     "Ack",
echo     "Decision",
echo     "PlanAck",
echo     "Safety",
echo     "TelemetryBatch",
echo     "TelemetryPoint",
echo     "TelemetryRef",
echo     "DecisionServiceServicer",
echo     "DecisionServiceStub",
echo     "add_DecisionServiceServicer_to_server",
echo ]
) > "%OUTPUT_DIR%\__init__.py"

echo Python stubs generated successfully in %OUTPUT_DIR%
echo.
echo Proto generation complete

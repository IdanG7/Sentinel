# Testing Guide

This document describes how to run tests for the Sentinel project.

## Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio aiosqlite

# Install project dependencies
pip install -e libs/k8s-driver
pip install -e libs/policy-engine
```

## Running Tests

### Run All Tests
```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=libs --cov=services --cov-report=html
```

### Run Specific Test Suites

```bash
# Run only K8s driver tests
pytest libs/k8s-driver/tests/

# Run only Policy Engine tests
pytest libs/policy-engine/tests/

# Run only integration tests
pytest tests/integration/

# Run tests by marker
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
```

### Run Specific Test Files

```bash
# Run deployment tests
pytest libs/k8s-driver/tests/test_deployments.py

# Run policy engine tests
pytest libs/policy-engine/tests/test_engine.py

# Run with specific test function
pytest libs/policy-engine/tests/test_engine.py::TestPolicyEngine::test_evaluate_approve
```

## Test Coverage

### Generate Coverage Report

```bash
# Generate HTML coverage report
pytest --cov=libs --cov=services --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage by Component

```bash
# K8s driver coverage only
pytest libs/k8s-driver/tests/ --cov=libs/k8s-driver --cov-report=term-missing

# Policy engine coverage only
pytest libs/policy-engine/tests/ --cov=libs/policy-engine --cov-report=term-missing
```

## Test Markers

Tests are organized with markers for easy filtering:

- `unit` - Unit tests (fast, no external dependencies)
- `integration` - Integration tests (may require services)
- `slow` - Slow running tests
- `requires_k8s` - Tests that need a Kubernetes cluster

```bash
# Run only fast unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run integration tests
pytest -m integration
```

## Test Structure

```
tests/
├── conftest.py                 # Global fixtures
└── integration/
    └── test_deployment_flow.py # Integration tests

libs/k8s-driver/tests/
├── conftest.py                 # K8s driver fixtures
└── test_deployments.py         # Deployment manager tests

libs/policy-engine/tests/
├── conftest.py                 # Policy engine fixtures
└── test_engine.py              # Policy engine tests
```

## Writing Tests

### Unit Test Example

```python
import pytest
from sentinel_k8s import DeploymentManager

def test_create_deployment(mock_cluster, sample_deployment_spec):
    """Test creating a deployment."""
    manager = DeploymentManager(mock_cluster)
    result = manager.create(sample_deployment_spec)

    assert result is not None
    assert result.metadata.name == "test-deployment"
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_workflow(test_db):
    """Test database operations."""
    from app.crud import workload as workload_crud

    workload = await workload_crud.create(test_db, obj_in=workload_data)
    assert workload.id is not None
```

## Continuous Integration

Tests run automatically on:
- Every push to main
- Every pull request
- Scheduled daily builds

CI configuration: `.github/workflows/tests.yml`

## Troubleshooting

### Tests Failing Locally

```bash
# Clean up pytest cache
pytest --cache-clear

# Run with detailed output
pytest -vv --tb=long

# Run specific failing test with debug
pytest tests/path/to/test.py::test_name -vv --tb=long --pdb
```

### Database Tests Failing

```bash
# Ensure test database dependencies installed
pip install aiosqlite

# Run with async test support
pip install pytest-asyncio
```

### Import Errors

```bash
# Reinstall libraries in development mode
pip install -e libs/k8s-driver
pip install -e libs/policy-engine

# Verify installation
python -c "import sentinel_k8s; print(sentinel_k8s.__version__)"
python -c "import sentinel_policy; print(sentinel_policy.__version__)"
```

## Performance Testing

```bash
# Run tests with profiling
pytest --profile

# Run with execution time
pytest --durations=10  # Show 10 slowest tests
```

## Test Data

### Fixtures Available

- `mock_cluster_connection` - Mock Kubernetes cluster
- `sample_deployment_spec` - Example deployment specification
- `sample_job_spec` - Example job specification
- `sample_policy` - Example policy with rules
- `sample_action_plan` - Example action plan
- `test_db` - Test database (SQLite in-memory)
- `mock_kafka_producer` - Mock Kafka producer
- `mock_policy_engine` - Mock policy engine

### Creating Test Data

```python
@pytest.fixture
def my_custom_fixture():
    """Custom test fixture."""
    data = create_test_data()
    yield data
    cleanup_test_data(data)
```

## Best Practices

1. **Isolate Tests** - Each test should be independent
2. **Use Fixtures** - Reuse common test setup
3. **Mock External Services** - Don't depend on real K8s, Kafka, etc.
4. **Test Edge Cases** - Include error scenarios
5. **Keep Tests Fast** - Unit tests should run in milliseconds
6. **Clear Test Names** - Use descriptive test function names
7. **Assert Specifically** - Test exact expected behavior

## Expected Test Results

```
=================== test session starts ===================
collected 40 items

libs/k8s-driver/tests/test_deployments.py ........  [ 20%]
libs/policy-engine/tests/test_engine.py ...........  [ 47%]
tests/integration/test_deployment_flow.py .....   [100%]

---------- coverage: platform darwin, python 3.11.7 ----------
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
libs/k8s-driver/sentinel_k8s           250     15    94%
libs/policy-engine/sentinel_policy     180     10    94%
-----------------------------------------------------------
TOTAL                                  430     25    94%

================= 40 passed in 2.34s =================
```

## Next Steps

- Add more integration tests for API endpoints
- Add performance benchmarks
- Add chaos testing scenarios
- Increase coverage to 95%+

---

For more information, see `PHASE1_COMPLETE.md`

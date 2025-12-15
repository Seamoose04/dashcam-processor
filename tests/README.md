# Test Suite Structure

This directory contains comprehensive unit and integration tests for the dashcam processor system.

## Directory Structure

```
tests/
├── __init__.py
├── test_models.py              # Unit tests for SQLAlchemy models (Task, Device, InputOutput)
├── test_task_manager.py        # Unit tests for TaskManager service
├── test_device_registry.py     # Unit tests for DeviceRegistry service
├── test_config.py              # Unit tests for ConfigurationLoader
├── integration/
│   ├── __init__.py
│   ├── test_task_lifecycle.py  # Integration tests for task lifecycle management
│   └── test_adapters.py        # Integration tests for device adapters
└── fixtures/                  # Test data and sample configurations
    └── sample_config.json      # Sample configuration file for testing
```

## Running Tests

To run the complete test suite:

```bash
pytest tests/
```

### Running Specific Test Files

```bash
# Run all unit tests
pytest tests/test_*.py

# Run integration tests only
pytest tests/integration/

# Run specific test class
pytest tests/test_models.py::TestTaskModel -v

# Run specific test method
pytest tests/test_task_manager.py::TestTaskManager::test_create_task_valid -v
```

## Test Coverage

### Unit Tests

- **`test_models.py`**: Tests for SQLAlchemy model definitions
  - Task model creation and serialization
  - InputOutput model relationships
  - Device model capabilities and status tracking

- **`test_task_manager.py`**: Tests for task management functionality
  - Task creation with validation
  - Pending task retrieval and filtering
  - Task completion and state transitions
  - Task listing and counting

- **`test_device_registry.py`**: Tests for device registration and management
  - Device registration and updates
  - Heartbeat tracking and timeout handling
  - Online/offline status transitions
  - Device type filtering and capability queries

- **`test_config.py`**: Tests for configuration loading and validation
  - Global configuration reading and writing
  - Device-specific configuration management
  - Configuration validation rules
  - Deep merge functionality for nested configurations

### Integration Tests

- **`integration/test_task_lifecycle.py`**: End-to-end workflow tests
  - Complete task lifecycle from creation to completion
  - Task state transitions across pipeline stages
  - Device capability matching and filtering
  - Error handling in task processing

- **`integration/test_adapters.py`**: Device adapter integration tests
  - Multiple device registration of same type
  - Online/offline status management
  - Task assignment based on capabilities
  - Heartbeat timeout detection
  - Device type to task type mapping

## Test Fixtures

The `fixtures/` directory contains sample data used in tests:

- **`sample_config.json`**: Example configuration file with all required sections

## Validation Scripts

See the [`scripts/`](scripts/) directory for deployment validation tools:
- [`validate_config.py`](scripts/validate_config.py): Validates configuration files before deployment
- [`health_check.py`](scripts/health_check.py): Comprehensive system health checks

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Mocking**: Use mocks for external dependencies (database, filesystem)
3. **Edge Cases**: Test error conditions and boundary cases
4. **Documentation**: Clear docstrings explaining what each test verifies
5. **Performance**: Tests should run quickly to encourage frequent execution

## Adding New Tests

When adding new functionality:

1. Create a new test file following the naming convention `test_*.py`
2. Add unit tests for individual components
3. Add integration tests for end-to-end workflows
4. Update this README with descriptions of new tests

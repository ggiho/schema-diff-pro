# Schema Diff Pro Tests

This directory contains tests for the Schema Diff Pro application, including unit tests and integration tests for the SSH tunnel functionality and environment detection.

## Test Structure

- **test_environment.py**: Unit tests for environment detection and SSH tunnel configuration
- **test_integration.py**: Integration tests for API endpoints and system functionality  
- **run_tests.sh**: Test runner script that works in both Docker and local environments
- **README.md**: This documentation file

## Running Tests

### Quick Start
```bash
# Make sure you're in the tests directory
cd tests

# Run all tests
./run_tests.sh
```

### Individual Test Files

#### Unit Tests
```bash
# Run environment and configuration tests
python -m pytest test_environment.py -v

# Install dependencies if needed
pip install pytest pytest-asyncio
```

#### Integration Tests  
```bash
# Run integration tests (requires running backend)
python test_integration.py
```

## Test Requirements

### Prerequisites
- Python 3.9+
- Backend server running (for integration tests)
- Required Python packages:
  - pytest
  - pytest-asyncio
  - aiohttp

### Environment Variables
The tests automatically detect the environment:
- **Docker**: `DOCKER_ENV=true` → Tests API at `http://backend:8000`
- **Local**: No `DOCKER_ENV` → Tests API at `http://localhost:8000`

## Test Coverage

### Environment Detection Tests
- ✅ Docker environment detection
- ✅ Local environment detection
- ✅ API URL configuration

### SSH Tunnel Configuration Tests
- ✅ SSH tunnel config creation and validation
- ✅ Different authentication methods (password, private key, SSH agent)
- ✅ Configuration validation (required fields, format validation)
- ✅ SSH tunnel manager functionality

### Integration Tests
- ✅ API health check
- ✅ SSH system status
- ✅ Database connection testing
- ✅ SSH key validation
- ✅ Environment-specific API URL handling

## Test Results Interpretation

### Expected Results
- **Unit Tests**: Should all pass if SSH tunnel models and validation are working correctly
- **Integration Tests**: 
  - API Health: Should pass if backend is running
  - SSH Status: May show "asyncssh not available" in test environment (expected)
  - Database Connection: Will fail without valid database (expected for testing)
  - SSH Key Validation: Will test validation logic (expected to handle invalid keys)

### Common Issues
1. **AsyncSSH Not Available**: Normal in test environments, SSH functionality requires `asyncssh` package
2. **Database Connection Failed**: Expected when testing with invalid credentials  
3. **API Connection Failed**: Check if backend server is running on expected port

## Development Usage

When developing new SSH tunnel features:

1. Add unit tests to `test_environment.py`
2. Add integration tests to `test_integration.py`  
3. Run tests with `./run_tests.sh`
4. Update this README with new test coverage

## CI/CD Integration

This test suite is designed to work in both local development and Docker environments:

```bash
# In Docker Compose
docker-compose exec backend python /app/tests/run_tests.sh

# Local development
cd tests && ./run_tests.sh
```
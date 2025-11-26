# faff-cli Test Suite

This directory contains comprehensive tests for faff-cli at multiple levels:
- Unit tests for utility functions
- CLI command tests using Typer's test client
- Integration tests for end-to-end workflows

## Running Tests

### Install Test Dependencies

```bash
# Install development dependencies
pip install -e ".[dev]"
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_utils.py

# Run specific test class
pytest tests/test_cli_log.py::TestLogShowCommand

# Run specific test
pytest tests/test_utils.py::TestResolveNaturalDate::test_iso_date_string
```

### Coverage Reports

```bash
# Generate HTML coverage report (opens in browser)
pytest --cov=faff_cli --cov-report=html
open htmlcov/index.html

# Generate terminal coverage report
pytest --cov=faff_cli --cov-report=term-missing
```

### Watch Mode (for development)

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw
```

## Test Structure

### `conftest.py`
Shared fixtures used across all tests:
- `temp_faff_dir` - Temporary .faff directory for isolated testing
- `workspace` - Workspace instance pointed at temp directory
- `sample_intent` - Sample Intent objects for testing
- `workspace_with_plan` - Pre-configured workspace with a plan
- `workspace_with_log` - Pre-configured workspace with log entries

### `test_utils.py`
Unit tests for `faff_cli.utils` module:
- Date parsing with `resolve_natural_date()`
- File editing functionality
- Edge cases and error handling

### `test_file_utils.py`
Unit tests for `faff_cli.file_utils` module:
- Finding .faff root directory
- Initializing repositories
- Path resolution for logs, plans, configs

### `test_models.py`
Tests for faff_core data models:
- Intent creation and validation
- Plan loading from TOML files
- Tracker management

### `test_cli_status.py`
CLI tests for status and basic commands:
- `faff status` - shows version, repo location, active session
- `faff init` - initializes new repositories
- `faff config` - configuration management

### `test_cli_log.py`
CLI tests for log commands:
- `faff log show` - display log files
- `faff log list` - list all logs
- `faff log summary` - summarize time by intent/tracker
- `faff log refresh` - reformat log files
- `faff stop` - stop active session

### `test_cli_plan.py`
CLI tests for plan commands:
- `faff plan list` - list active plans
- `faff plan show` - show plan details
- `faff plan remotes` - list plan sources
- `faff plan pull` - pull plans from remotes

### `test_integration.py`
End-to-end workflow tests:
- Basic workflows (init → status → log)
- Plan management workflows
- Log viewing and summary workflows
- Error handling scenarios
- Data persistence verification

## Writing New Tests

### Use Fixtures for Setup

```python
def test_my_feature(workspace, sample_intent):
    """Always use fixtures instead of manual setup."""
    # workspace and sample_intent are ready to use
    workspace.logs.start_intent_now(sample_intent, None)
    assert workspace.logs.get_log(workspace.today()).active_session()
```

### CLI Tests Use CliRunner

```python
from typer.testing import CliRunner
from faff_cli.main import cli

runner = CliRunner()

def test_command(temp_faff_dir, monkeypatch):
    monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))
    result = runner.invoke(cli, ["command", "arg"])
    assert result.exit_code == 0
    assert "expected output" in result.stdout
```

### Test Isolation

Each test should:
- Use `temp_faff_dir` fixture for file operations
- Not depend on other tests
- Clean up after itself (fixtures handle this)
- Mock external dependencies

### Coverage Goals

- **Unit tests**: Test individual functions with various inputs
- **CLI tests**: Test command parsing and output
- **Integration tests**: Test realistic user workflows
- Target: >80% code coverage

## Common Issues

### ImportError: faff_core not found
```bash
# Install faff-core in development mode
cd ../faff-core-rust/bindings-python
maturin develop
```

### Tests fail with "No module named 'faff_cli'"
```bash
# Install faff-cli in development mode
pip install -e .
```

### "FAFF_ROOT not set" errors
The tests use `monkeypatch.setenv("FAFF_ROOT", ...)` to set this.
If you're seeing this error, ensure you're using the `temp_faff_dir` fixture
and patching the environment variable.

### Editor tests hang
Tests for `edit_file()` mock the subprocess call. If tests hang, check
that `monkeypatch.setattr("subprocess.run", mock_run)` is working correctly.

## Continuous Integration

The test suite is designed to run in CI environments:
- All tests use temporary directories (no system state)
- No network calls (plan remotes are mocked/local)
- Fast execution (< 10 seconds for full suite)
- Clear failure messages

## Test Coverage Areas

### ✅ Currently Tested
- Date parsing and natural language dates
- File system utilities (find root, init repo, path resolution)
- Basic CLI commands (status, init, config)
- Log commands (show, list, summary, refresh)
- Plan commands (list, show, remotes, pull)
- Integration workflows
- Data persistence

### 🚧 Needs More Coverage
- `faff start` command (requires mocking fuzzy select UI)
- `faff stop` with active sessions
- `faff compile` timesheet compilation
- Query command with filters
- Error handling for corrupted data files
- Timezone edge cases
- Plugin system (if exposed in CLI)

### ❌ Not Yet Tested
- Interactive UI components (fuzzy_select)
- Editor integration (hard to test subprocess)
- Timesheet signing and submission
- Remote plan sources (beyond local)
- Migration scripts

## Contributing Tests

When adding new features:
1. Write tests first (TDD) or alongside the feature
2. Include unit, CLI, and integration tests
3. Update this README if adding new test files
4. Ensure all tests pass before committing
5. Maintain or improve coverage percentage

## Questions?

See the main TODO.md for testing-related tasks and priorities.

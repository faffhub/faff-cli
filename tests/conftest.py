"""
Shared pytest fixtures for faff-cli tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime
import zoneinfo

from faff_core import Workspace
from faff_core.models import Intent, Plan


@pytest.fixture
def temp_faff_dir():
    """
    Create a temporary .faff directory for testing.
    Automatically cleans up after the test.
    """
    temp_dir = tempfile.mkdtemp(prefix="faff_test_")
    faff_dir = Path(temp_dir) / ".faff"
    faff_dir.mkdir(parents=True)

    # Create subdirectories
    (faff_dir / "logs").mkdir()
    (faff_dir / "plans").mkdir()
    (faff_dir / "timesheets").mkdir()
    (faff_dir / "identities").mkdir()

    # Create a minimal config.toml
    config_content = """
[workspace]
timezone = "UTC"

[[sources]]
id = "local"
type = "local"
"""
    (faff_dir / "config.toml").write_text(config_content)

    yield faff_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def workspace(temp_faff_dir, monkeypatch):
    """
    Create a Workspace instance pointed at the temp directory.
    """
    # Monkeypatch the environment to use temp directory
    monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

    # Create workspace
    ws = Workspace()
    return ws


@pytest.fixture
def sample_intent():
    """
    Create a sample Intent for testing.
    """
    return Intent(
        alias="test-task",
        role="developer",
        objective="testing",
        action="writing",
        subject="tests",
        trackers=["project:test"]
    )


@pytest.fixture
def sample_intent_alt():
    """
    Create an alternative Intent for testing.
    """
    return Intent(
        alias="other-task",
        role="developer",
        objective="development",
        action="implementing",
        subject="feature",
        trackers=["project:main"]
    )


@pytest.fixture
def sample_plan_toml():
    """
    Return TOML content for a sample plan.
    """
    return """
source = "local"
valid_from = "2025-01-01"

[[trackers]]
id = "project:test"
name = "Test Project"

[[trackers]]
id = "project:main"
name = "Main Project"

[roles]
"work:eng" = "Software Engineer"
"work:lead" = "Tech Lead"

[objectives]
"dev:feature" = "Feature Development"
"dev:bugfix" = "Bug Fixing"

[actions]
"code:write" = "Writing Code"
"code:review" = "Reviewing Code"

[subjects]
"proj:api" = "API Development"
"proj:ui" = "UI Development"
"""


@pytest.fixture
def workspace_with_plan(workspace, temp_faff_dir, sample_plan_toml):
    """
    Create a workspace with a sample plan already loaded.
    """
    # Plan is valid from 2025-03-20 per sample_plan_toml
    plan_file = temp_faff_dir / "plans" / "local-20250320.toml"
    plan_file.write_text(sample_plan_toml)
    return workspace


@pytest.fixture
def workspace_with_log(workspace, temp_faff_dir):
    """
    Create a workspace with a log entry for today.
    """
    today = workspace.today()
    intent = Intent(
        alias="existing-task",
        role="developer",
        objective="testing",
        action="coding",
        subject="tests",
        trackers=[]
    )

    # Start and stop a session
    workspace.logs.start_intent_now(intent, None)
    workspace.logs.stop_current_session()

    # Write the log file so it persists
    log = workspace.logs.get_log_or_create(today)
    trackers = workspace.plans.get_trackers(today)
    workspace.logs.write_log(log, trackers)

    return workspace


@pytest.fixture
def fixed_date():
    """
    Return a fixed date for testing date-dependent functionality.
    """
    return date(2025, 1, 15)


@pytest.fixture
def fixed_datetime():
    """
    Return a fixed datetime for testing time-dependent functionality.
    """
    return datetime(2025, 1, 15, 14, 30, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))


@pytest.fixture
def sample_log_toml():
    """
    Return TOML content for a sample log file.
    """
    return """
date = "2025-01-15"
timezone = "UTC"

[[timeline]]
start = "09:00:00"
end = "10:30:00"
intent_id = "i-20250115-abc123"
alias = "morning-standup"
role = "work:eng"
objective = "dev:sync"
action = "meeting:attend"
subject = "team:standup"
trackers = ["project:main"]

[[timeline]]
start = "10:30:00"
end = "12:00:00"
intent_id = "i-20250115-def456"
alias = "feature-work"
role = "work:eng"
objective = "dev:feature"
action = "code:write"
subject = "proj:api"
trackers = ["project:main"]
"""

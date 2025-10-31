"""
Tests for faff_core models and data structures.
"""
import pytest
from pathlib import Path
from datetime import date

from faff_core.models import Intent, Plan


class TestIntent:
    """Test Intent model."""

    def test_create_intent_with_all_fields(self):
        """Should create intent with all fields populated."""
        intent = Intent(
            alias="test-task",
            role="developer",
            objective="testing",
            action="writing",
            subject="tests",
            trackers=["project:test"]
        )

        assert intent.alias == "test-task"
        assert intent.role == "developer"
        assert intent.objective == "testing"
        assert intent.action == "writing"
        assert intent.subject == "tests"
        assert intent.trackers == ["project:test"]
        # intent_id is empty until added to a plan
        assert intent.intent_id == ""

    def test_create_intent_minimal(self):
        """Should create intent with minimal fields."""
        intent = Intent(alias="simple-task")

        assert intent.alias == "simple-task"
        assert intent.role is None
        assert intent.objective is None
        assert intent.intent_id is not None

    def test_intent_with_multiple_trackers(self):
        """Should handle multiple trackers."""
        intent = Intent(
            alias="multi-tracker-task",
            trackers=["project:a", "project:b", "client:x"]
        )

        assert len(intent.trackers) == 3
        assert "project:a" in intent.trackers


class TestPlanFromFile:
    """Test Plan model file operations."""

    def test_plan_from_toml_file(self):
        """Should parse plan from TOML file."""
        import toml
        test_file = Path("tests/testdata/sample_plan.toml")

        # Load TOML and create Plan from dict
        data = toml.load(test_file)
        plan = Plan.from_dict(data)

        assert plan.source == "local"
        assert plan.valid_from == date(2025, 3, 20)
        assert plan.valid_until == date(2025, 4, 1)

    def test_plan_has_trackers(self):
        """Should load trackers from plan file."""
        import toml
        test_file = Path("tests/testdata/sample_plan.toml")

        # Load TOML and create Plan from dict
        data = toml.load(test_file)
        plan = Plan.from_dict(data)

        # The sample plan has 2 trackers - trackers is a Dict property
        assert len(plan.trackers) >= 2
        assert "work:admin" in plan.trackers or "client:projectx" in plan.trackers

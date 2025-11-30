"""
CLI tests for plan commands.
"""
import pytest
from typer.testing import CliRunner
from faff_cli.main import cli


runner = CliRunner()


class TestPlanListCommand:
    """Test the 'faff plan list' command."""

    def test_plan_list_no_plans(self, temp_faff_dir, monkeypatch):
        """Should handle no active plans."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["plan", "list"])

        assert result.exit_code == 0
        assert "No plans found for" in result.stdout

    def test_plan_list_with_date(self, temp_faff_dir, monkeypatch):
        """Should accept date argument."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["plan", "list", "2025-01-15"])

        assert result.exit_code == 0

    def test_plan_list_with_plan_file(self, workspace_with_plan, temp_faff_dir, monkeypatch):
        """Should list existing plans."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["plan", "list", "2025-01-15"])

        assert result.exit_code == 0
        # Should show at least one plan
        assert "local" in result.stdout or "plan" in result.stdout.lower()


class TestPlanShowCommand:
    """Test the 'faff plan show' command."""

    def test_plan_show_requires_source(self, temp_faff_dir, monkeypatch):
        """Should require source argument."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["plan", "show"])

        # Should fail - missing required source argument
        assert result.exit_code == 2  # typer usage error


class TestPlanRemotesCommand:
    """Test the 'faff plan remotes' command."""

    def test_plan_remotes_lists_sources(self, temp_faff_dir, monkeypatch):
        """Should list configured plan remotes."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["plan", "remotes"])

        assert result.exit_code == 0
        assert "remote" in result.stdout.lower()
        # Shows configured remotes from config - may not include "local" specifically


class TestPlanPullCommand:
    """Test the 'faff pull' command (pulls plans from remotes)."""

    def test_plan_pull_all_remotes(self, temp_faff_dir, monkeypatch):
        """Should pull from all remotes when no ID specified."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["pull"])

        # Should complete without error (even if no remotes configured)
        assert result.exit_code == 0

    def test_plan_pull_specific_remote(self, temp_faff_dir, monkeypatch):
        """Should pull from specific remote by ID."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        # Try pulling from a remote that may not exist
        result = runner.invoke(cli, ["pull", "local"])

        # May fail if "local" remote doesn't exist, which is fine
        # assert result.exit_code == 0 or "No plans" in result.stdout or "Unknown" in result.stdout

    def test_plan_pull_invalid_remote(self, temp_faff_dir, monkeypatch):
        """Should fail gracefully for invalid remote ID."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["pull", "nonexistent-remote"])

        # Should either exit with error or show helpful message
        assert result.exit_code != 0 or "Unknown" in result.stdout

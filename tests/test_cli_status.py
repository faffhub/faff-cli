"""
CLI tests for status and basic commands.
"""
import pytest
from typer.testing import CliRunner
from faff_cli.main import cli


runner = CliRunner()


class TestStatusCommand:
    """Test the 'faff status' command."""

    def test_status_shows_version(self, temp_faff_dir, monkeypatch):
        """Should display faff-core version."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "faff-core version:" in result.stdout

    def test_status_shows_repo_location(self, temp_faff_dir, monkeypatch):
        """Should display repository location."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Ledger:" in result.stdout

    def test_status_shows_no_active_session(self, temp_faff_dir, monkeypatch):
        """Should indicate when not working on anything."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Not currently working on anything" in result.stdout

    def test_status_shows_total_time(self, temp_faff_dir, monkeypatch):
        """Should display total recorded time for today."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total recorded time for today" in result.stdout


class TestInitCommand:
    """Test the 'faff init' command."""

    def test_init_creates_faff_directory(self, tmp_path):
        """Should create faff directory structure."""
        result = runner.invoke(cli, ["init"], env={"FAFF_DIR": str(tmp_path)})

        assert result.exit_code == 0
        assert (tmp_path / "logs").exists()
        assert (tmp_path / "plans").exists()
        assert (tmp_path / "config.toml").exists()
        assert "Initialized faff ledger" in result.stdout

    def test_init_fails_when_already_exists(self, tmp_path):
        """Should fail when ledger already initialized."""
        # Initialize once
        runner.invoke(cli, ["init"], env={"FAFF_DIR": str(tmp_path)})

        # Try to initialize again
        result = runner.invoke(cli, ["init"], env={"FAFF_DIR": str(tmp_path)})

        assert result.exit_code == 1
        assert "already initialized" in result.stdout


class TestConfigCommand:
    """Test the 'faff config' command."""

    def test_config_command_exists(self, temp_faff_dir, monkeypatch):
        """Should have a config command."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        # This will try to open an editor, which we can't test easily
        # Just verify the command exists and responds
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

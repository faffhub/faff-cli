"""
CLI tests for status and basic commands.
"""
import pytest
from typer.testing import CliRunner
from faff_cli.main import cli


runner = CliRunner()


class TestStatusCommand:
    """Test the 'faff status' command."""

    def test_status_shows_plans_section(self, temp_faff_dir, monkeypatch):
        """Should display Plans section."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Plans:" in result.stdout

    def test_status_shows_today_section(self, temp_faff_dir, monkeypatch):
        """Should display Today section with tracking info."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Today:" in result.stdout

    def test_status_shows_no_active_session(self, temp_faff_dir, monkeypatch):
        """Should indicate when not tracking anything."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Not tracking" in result.stdout

    def test_status_shows_compile_section(self, temp_faff_dir, monkeypatch):
        """Should display Logs to Compile section."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Logs to Compile:" in result.stdout

    def test_status_shows_push_section(self, temp_faff_dir, monkeypatch):
        """Should display Timesheets to Push section."""
        monkeypatch.setenv("FAFF_DIR", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Timesheets to Push:" in result.stdout


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

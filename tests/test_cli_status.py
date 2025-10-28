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
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "faff-core library version" in result.stdout

    def test_status_shows_repo_location(self, temp_faff_dir, monkeypatch):
        """Should display repository location."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Status for faff repo root at:" in result.stdout

    def test_status_shows_no_active_session(self, temp_faff_dir, monkeypatch):
        """Should indicate when not working on anything."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Not currently working on anything" in result.stdout

    def test_status_shows_total_time(self, temp_faff_dir, monkeypatch):
        """Should display total recorded time for today."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total recorded time for today" in result.stdout


class TestInitCommand:
    """Test the 'faff init' command."""

    def test_init_creates_faff_directory(self, tmp_path):
        """Should create .faff directory structure."""
        result = runner.invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / ".faff").exists()
        assert (tmp_path / ".faff" / "logs").exists()
        assert (tmp_path / ".faff" / "plans").exists()
        assert "Initialised faff repository" in result.stdout

    def test_init_fails_on_nonexistent_directory(self):
        """Should fail when target directory doesn't exist."""
        result = runner.invoke(cli, ["init", "/nonexistent/path/xyz"])

        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_init_with_force_flag(self, tmp_path):
        """Should accept --force flag."""
        # Create parent .faff
        parent_faff = tmp_path / ".faff"
        parent_faff.mkdir()

        # Try to init subdirectory with force
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = runner.invoke(cli, ["init", str(subdir), "--force"])

        assert result.exit_code == 0
        assert (subdir / ".faff").exists()


class TestConfigCommand:
    """Test the 'faff config' command."""

    def test_config_command_exists(self, temp_faff_dir, monkeypatch):
        """Should have a config command."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        # This will try to open an editor, which we can't test easily
        # Just verify the command exists and responds
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "config" in result.stdout.lower()

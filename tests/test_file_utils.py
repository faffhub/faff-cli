"""
Unit tests for faff_cli.file_utils module.
"""
import pytest
from pathlib import Path
from faff_cli.file_utils import FileSystemUtils


class TestFileSystemUtils:
    """Test FileSystemUtils class methods."""

    def test_find_faff_root_in_current_dir(self, tmp_path, monkeypatch):
        """Should find .faff in current directory."""
        faff_dir = tmp_path / ".faff"
        faff_dir.mkdir()

        monkeypatch.chdir(tmp_path)

        result = FileSystemUtils.find_faff_root(tmp_path)
        assert result == tmp_path

    def test_find_faff_root_in_parent_dir(self, tmp_path, monkeypatch):
        """Should find .faff in parent directory."""
        faff_dir = tmp_path / ".faff"
        faff_dir.mkdir()

        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        result = FileSystemUtils.find_faff_root(subdir)
        assert result == tmp_path

    def test_find_faff_root_not_found(self, tmp_path):
        """Should raise FileNotFoundError when .faff is not found."""
        with pytest.raises(FileNotFoundError):
            FileSystemUtils.find_faff_root(tmp_path)

    def test_initialise_repo_creates_structure(self, tmp_path):
        """Should create .faff directory structure."""
        FileSystemUtils.initialise_repo(tmp_path, force=False)

        faff_dir = tmp_path / ".faff"
        assert faff_dir.exists()
        assert (faff_dir / "logs").exists()
        assert (faff_dir / "plans").exists()
        assert (faff_dir / "timesheets").exists()
        assert (faff_dir / "keys").exists()  # 'keys' not 'identities'
        assert (faff_dir / "config.toml").exists()

    def test_initialise_repo_creates_config(self, tmp_path):
        """Should create valid config.toml (empty file initially)."""
        FileSystemUtils.initialise_repo(tmp_path, force=False)

        config_file = tmp_path / ".faff" / "config.toml"
        # File is created empty, workspace populates it on first use
        assert config_file.exists()

    def test_initialise_repo_without_force_fails_in_nested(self, tmp_path):
        """Should fail when initializing inside existing faff repo without force."""
        # Create parent repo
        faff_dir = tmp_path / ".faff"
        faff_dir.mkdir()

        # Try to init in subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(Exception):
            FileSystemUtils.initialise_repo(subdir, force=False)

    def test_initialise_repo_with_force_succeeds_in_nested(self, tmp_path):
        """Should succeed when initializing inside existing repo with force=True."""
        # Create parent repo
        faff_dir = tmp_path / ".faff"
        faff_dir.mkdir()

        # Init in subdirectory with force
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        FileSystemUtils.initialise_repo(subdir, force=True)

        assert (subdir / ".faff").exists()

    def test_get_faff_root_returns_path(self, temp_faff_dir, monkeypatch):
        """Should return the faff root directory."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        root = FileSystemUtils.get_faff_root()
        assert root is not None
        assert Path(root).exists()

    def test_get_config_path(self, temp_faff_dir, monkeypatch):
        """Should return path to config.toml."""
        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        config_path = FileSystemUtils.get_config_path()
        assert config_path.name == "config.toml"
        assert config_path.exists()

    def test_get_log_path(self, temp_faff_dir, monkeypatch):
        """Should return path for a log file."""
        from datetime import date

        monkeypatch.setenv("FAFF_ROOT", str(temp_faff_dir))

        test_date = date(2025, 1, 15)
        log_path = FileSystemUtils.get_log_path(test_date)

        assert log_path.parent.name == "logs"
        # Uses ISO format: 2025-01-15.toml
        assert "2025-01-15" in str(log_path)
        assert log_path.suffix == ".toml"

"""File system utilities for faff CLI operations"""

import os
from pathlib import Path


class FileSystemUtils:
    """Utilities for file system operations needed by the CLI"""

    ROOT_NAME = ".faff"

    VALID_DIRECTORY_STRUCTURE: dict[str, dict[str, None | dict]] = {
        '.faff': {
            'config.toml': None,
            'intents': {},
            'keys': {},
            'plans': {},
            'plugins': {},
            'plugin_state': {},
            'logs': {},
            'timesheets': {},
        }
    }

    @classmethod
    def find_faff_root(cls, search_start: Path) -> Path:
        """
        Search upwards from a given path for a `.faff` directory.

        Args:
            search_start (Path): The path to start searching from.

        Returns:
            Path: The path to the directory containing `.faff`.

        Raises:
            FileNotFoundError: If no `.faff` directory is found in the path hierarchy.
        """
        possible_root = search_start

        while True:
            subdirs = [
                fname
                for fname in os.listdir(possible_root)
                if os.path.isdir(os.path.join(possible_root, fname))
            ]
            if cls.ROOT_NAME in subdirs:
                return possible_root
            else:
                next_possible_root = Path(possible_root).parent.absolute()
                if next_possible_root == possible_root:
                    raise FileNotFoundError(
                        f"No {cls.ROOT_NAME} directory found from start {search_start}.")
                else:
                    possible_root = next_possible_root

    @classmethod
    def get_faff_root(cls) -> Path:
        """Get the faff root directory starting from current working directory"""
        return cls.find_faff_root(Path.cwd())

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file"""
        return cls.get_faff_root() / ".faff" / "config.toml"

    @classmethod
    def get_log_path(cls, date) -> Path:
        """Get the path to a log file for a given date"""
        return cls.get_faff_root() / ".faff" / "logs" / f"{date.isoformat()}.toml"

    @classmethod
    def initialise_repo(cls, target_dir: Path, force: bool = False) -> None:
        """
        Initialise a new `.faff` directory in the target directory.

        Args:
            target_dir: Directory to initialize the faff repo in
            force: Allow initialization inside a parent faff repo
        """
        from faff_cli.exceptions import NestedRepoExistsError

        try:
            already_initialised = cls.find_faff_root(target_dir)
        except FileNotFoundError:
            # We're actually expecting there not to be a faff root in this case.
            already_initialised = None

        if already_initialised == target_dir:
            raise FileExistsError(
                f"Target directory {already_initialised} already contains a {cls.ROOT_NAME} directory.")

        if already_initialised and not force:
            raise NestedRepoExistsError(already_initialised)

        cls._create_directory_structure(cls.VALID_DIRECTORY_STRUCTURE, target_dir)

    @classmethod
    def _create_directory_structure(cls, directory_structure: dict, base_path: Path) -> None:
        """
        Recursively create directory structure from a dictionary object.
        """
        for name, value in directory_structure.items():
            path = os.path.join(base_path, name)

            if isinstance(value, dict):
                # Create directory if it doesn't exist
                if not os.path.exists(path):
                    os.makedirs(path)
                # Recursively create directory structure
                cls._create_directory_structure(value, Path(path))
            else:
                # Create file if it doesn't exist
                if not os.path.exists(path):
                    with open(path, "w") as _:
                        pass

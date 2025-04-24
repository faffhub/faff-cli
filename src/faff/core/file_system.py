import pendulum


import os
from pathlib import Path


class FileSystem:
    ROOT_NAME = ".faff"
    VALID_DIRECTORY_STRUCTURE = {
        '.faff': {
            'config.toml': None,
            'plans': {},
            'plugins': {},
            'plugin_state': {},
            'logs': {},
            'timesheets': {},
        }
    }

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or Path.cwd()

        self.FAFF_ROOT = self.find_faff_root()
        self.LOG_PATH = self.FAFF_ROOT / ".faff" / "logs"
        self.PLAN_PATH = self.FAFF_ROOT / ".faff" / "plans"
        self.PLUGIN_PATH = self.FAFF_ROOT / ".faff" / "plugins"
        self.PLUGIN_STATE_PATH = self.FAFF_ROOT / ".faff" / "plugin_state"
        self.CONFIG_PATH = self.FAFF_ROOT / ".faff" / "config.toml"

    # FIXME: this method name is confusing
    def log_path(self, date: pendulum.Date) -> Path:
        """
        Returns the path to the log file for the given date.
        """
        return self.LOG_PATH / f"{date.to_date_string()}.toml"

    def find_faff_root(self) -> Path:
        """
        Search upwards from a given path for a `.faff` directory.
        Args:
            start_path (Path): The path to start searching from.
        Returns:
            Path: The path to the directory containing `.faff`.
        Raises:
            FileNotFoundError: If no `.faff` directory is found in the path hierarchy.
        """
        possible_root = self.working_dir

        while True:
            subdirs = [
                fname
                for fname in os.listdir(possible_root)
                if os.path.isdir(os.path.join(possible_root, fname))
            ]
            if self.ROOT_NAME in subdirs:
                return possible_root
            else:
                next_possible_root = \
                    Path(possible_root).parent.absolute()
                if next_possible_root == possible_root:
                    raise FileNotFoundError(
                        f"No {self.ROOT_NAME} directory found from start {self.working_dir}.")
                else:
                    possible_root = next_possible_root

    # FIXME: This is a candidate for deletion. 
    def plan_files(self, date: pendulum.Date) -> list[Path]:
        import re
        PLAN_FILENAME_PATTERN = re.compile(r"(?P<source>.+?)\.(?P<datestr>\d{8})\.toml")

        candidates = {}

        for file in self.PLAN_PATH.glob("*.toml"):
            match = PLAN_FILENAME_PATTERN.match(file.name)
            source = match.group("source")
            try:
                file_date = pendulum.parse(match.group("datestr"), strict=True).date()
                if file_date > date:
                    print("continue")
                    continue
                if source not in candidates:
                    candidates[source] = file_date
                elif file_date > candidates.get(source):
                    candidates[source] = file_date
            except Exception:
                pass

        return [self.PLAN_PATH / Path(f'{source}.{date.format("YYYYMMDD")}.toml')
                for source, date in candidates.items()]

    def initialise_repo(self) -> None:
        """
        Initialise a new `.faff` directory in the current working directory.
        """
        try:
            already_initialised = self.find_faff_root()
        except FileNotFoundError:
            # We're actually expecting there not to be a faff root in this case.
            already_initialised = None

        if already_initialised:
            raise FileExistsError(
                f"Directory {already_initialised} already contains a {self.ROOT_NAME} directory.")  # noqa

        self._create_directory_structure(self.VALID_DIRECTORY_STRUCTURE, self.working_dir)

    def _create_directory_structure(self, directory_structure: dict,
                                    base_path : Path | None) -> None:
        """
        Recursively create directory structure from a dictionary object.
        """
        if base_path is None:
            base_path = self.working_dir

        for name, value in directory_structure.items():
            path = os.path.join(base_path, name)

            if isinstance(value, dict):
                # Create directory if it doesn't exist
                if not os.path.exists(path):
                    os.makedirs(path)
                # Recursively create directory structure
                self.create_directory_structure(value, path)
            else:
                # Create file if it doesn't exist
                if not os.path.exists(path):
                    with open(path, "w") as f:
                        pass
import os
import pendulum
from pathlib import Path

class Context:

    ROOT_NAME = ".faff"
    VALID_DIRECTORY_STRUCTURE = {
        '.faff': {
            'config.toml': None,
            'plans': {},
            'logs': {},
            'timesheets': {},
        }
    }

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or Path.cwd()

    def get_timezone(self) -> pendulum.Timezone:
        return pendulum.now().timezone # this should be configurable

    def today(self) -> pendulum.Date:
        #FIXME: Why is this funciton in context and core?
        return pendulum.today().date()

    def require_faff_root(self) -> Path:
        """
        Search upwards from a given path for a `.faff` directory.
        Args:
            start_path (Path): The path to start searching from.
        Returns:
            Path: The path to the directory containing `.faff`.
        Raises:
            FileNotFoundError: If no `.faff` directory is found in the path hierarchy.
        """
        path = self.find_faff_root()
        if path is None:
            raise FileNotFoundError(
                f"No {self.ROOT_NAME} directory found from start {self.working_dir}.")
        return path

    def find_faff_root(self) -> Path | None:
        """
        Search upwards from a given path for a `.faff` directory.
        Args:
            start_path (Path): The path to start searching from.
        Returns:
            Path | None: The path to the directory containing `.faff`, or None if not found.
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
                    return None
                else:
                    possible_root = next_possible_root

    def initialise_repo(self) -> None:
        """
        Initialise a new `.faff` directory in the current working directory.
        """
        already_initialised = self.find_faff_root()
        if already_initialised:
            raise FileExistsError(
                f"Directory {already_initialised} already contains a {self.ROOT_NAME} directory.")  # noqa

        self.create_directory_structure(self.VALID_DIRECTORY_STRUCTURE, self.working_dir)


    def create_directory_structure(self, directory_structure: dict,
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

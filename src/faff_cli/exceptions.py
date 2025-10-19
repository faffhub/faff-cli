"""Custom exceptions for faff CLI"""


class NestedRepoExistsError(Exception):
    """Raised when trying to initialize a faff repo inside an existing faff repo"""

    def __init__(self, parent_repo_path):
        self.parent_repo_path = parent_repo_path
        super().__init__(
            f"Cannot initialize faff repo inside existing repo at {parent_repo_path}. "
            "Use --force to override."
        )

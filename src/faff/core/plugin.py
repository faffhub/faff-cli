from __future__ import annotations

import pendulum

from slugify import slugify

from pathlib import Path
from typing import List, Dict, Any

from abc import ABC, abstractmethod

from faff.models import Log, TimeSheet

class Plugin(ABC):
    def __init__(self, plugin: str, name: str,
                 config: Dict[str, Any], state_path: Path):
        """
        Initialize the PullPlugin with configuration.

        Args:
            config (Dict[str, Any]): Configuration specific to the source.
        """
        self.plugin = plugin
        self.name = name
        self.state_path = state_path
        self.state_path.mkdir(parents=False, exist_ok=True)

        self.slug = slugify(self.name)
        self.config = config

class PullPlugin(Plugin):
    def filename(self, date: pendulum.Date) -> str:
        """
        Returns the filename for the plan file.

        Args:
            date (pendulum.Date): The date for which the plan is valid.

        Returns:
            str: The filename for the plan file.
        """
        date_str = date.format("YYYYMMDD")
        return f"remote.{self.slug}.{date_str}.toml"

    @abstractmethod
    def pull_plan(self, date: pendulum.Date) -> List[Dict[str, Any]]:
        """
        Fetches activities for a given day.

        Args:
            config (Dict[str, Any]): Configuration specific to the source.

        Returns:
            List[Dict[str, Any]]: List of activities formatted for Faff.
        """
        pass


class PushPlugin(Plugin):
    @abstractmethod
    def push_timesheet(self, config: Dict[str, Any], timesheet: Dict[str, Any]) -> None:
        """
        Pushes a compiled timesheet to a remote repository.

        Args:
            config (Dict[str, Any]): Configuration specific to the destination.
            timesheet (Dict[str, Any]): The compiled timesheet to push.
        """
        pass


class CompilePlugin(Plugin):
    @abstractmethod
    def compile_time_sheet(self, log: Log) -> TimeSheet:
        """
        Generates a report based on the provided log.

        Args:
            log (Log): The log to generate a report from.

        Returns:
            str: The generated report.
        """
        pass
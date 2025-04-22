from __future__ import annotations

import re
import os
import tomllib # We need this for fast loads.
import tomlkit # We need this for control over fancy human-readable writes.
import pendulum
import importlib

from slugify import slugify

from pathlib import Path
from typing import List, Dict, Type, Any, Callable, Optional

from abc import ABC, abstractmethod

from faff.models import Plan, Log, TimeSheet, Activity
from faff.models import Config

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


class TomlSerializer:

    @classmethod
    def serialize(cls, obj: Any) -> str:
        """
        Serializes a dataclass to a TOML string.
        This function handles nested dataclasses, lists, and dictionaries, and smells _ghastly_.
        XXX: Don't think about putting me in models.py though - models shouldn't worry about their
        representation as anything other than a pure dict.
        """
        from dataclasses import asdict

        def serialize_value(value):
            if isinstance(value, pendulum.DateTime):
                return value.to_iso8601_string()
            elif isinstance(value, pendulum.Date):
                return value.to_date_string()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(v) for v in value]
            else:
                return value
            
        def remove_none(obj):
            if isinstance(obj, dict):
                return {k: remove_none(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [remove_none(v) for v in obj]
            else:
                return obj

        # If obj is a dataclass, convert it to a dict
        if hasattr(obj, "__dataclass_fields__"):
            obj = asdict(obj)

        return tomlkit.dumps(
            remove_none(
                {k: serialize_value(v) for k, v in obj.items()}))


class LogFormatter:

    @classmethod
    def format_log(cls, log: Log, activities: List[Activity]) -> str:
        doc = tomlkit.document()
        doc.add(tomlkit.comment("This is a Faff-format log file - see faffage.com for details."))
        doc.add(tomlkit.comment("It has been generated but can be edited manually."))
        doc.add(tomlkit.comment("Changes to rows starting with '#' will not be saved."))

        # Add log data
        doc["date"] = log.date.to_date_string()
        doc["timezone"] = str(log.timezone)

        doc["--date_format"] = cls._get_datetime_format(log.date, log.timezone)

        # Add summary entries
        summary_array = []
        for entry in log.summary:
            activity = activities.get(entry.activity.id)
            summary_entry = tomlkit.table()
            summary_entry["activity"] = entry.activity.id
            if activity.project:
                summary_entry["--project"] = activity.project
            if activity.name:
                summary_entry["--name"] = activity.name
            summary_entry["duration"] = entry.duration
            if entry.note:
                summary_entry["note"] = entry.note
            summary_array.append(summary_entry)

        if len(summary_array) > 0:
            doc["summary"] = summary_array

        # Add timeline entries
        timeline_array = []

        for entry in sorted(log.timeline, key=lambda entry: entry.start):
            activity = activities.get(entry.activity.id)
            timeline_entry = tomlkit.table()
            timeline_entry["activity"] = entry.activity.id
            if activity.project:
                timeline_entry["--project"] = activity.project
            if activity.name:
                timeline_entry["--name"] = activity.name
            timeline_entry["start"] = entry.start.format(
                cls._get_datetime_format(log.date, log.timezone))
            if entry.end:
                timeline_entry["end"] = entry.end.format(
                    cls._get_datetime_format(log.date, log.timezone))
                interval = (entry.end - entry.start)
                duration = pendulum.duration(seconds=interval.total_seconds())
                timeline_entry["--duration"] = duration.in_words()
            if entry.note:
                timeline_entry["note"] = entry.note
            timeline_array.append(timeline_entry)
        
        if len(timeline_array) > 0:
            doc["timeline"] = timeline_array
        else:
            doc.add(tomlkit.nl())
            doc.add(tomlkit.comment("Timeline is empty."))

        # Convert the TOML document to a string
        toml_string = doc.as_string()

        # Align the `=` signs
        processed_toml = cls.commentify_derived_values(cls.align_equals(toml_string))

        return processed_toml

    @classmethod
    def commentify_derived_values(cls, toml_string: str) -> str:
        """
        Replace lines starting with '--' followed by a valid TOML variable name
        with a comment.

        Args:
            toml_string (str): The TOML string to process.

        Returns:
            str: The processed TOML string with matching lines replaced as comments.
        """
        # Regular expression to match lines like '--something = "some value"'
        pattern = r"^--([a-zA-Z_][a-zA-Z0-9_]*\s*=\s*.+)$"

        # Replace matching lines with comments
        processed_toml = re.sub(pattern, r"# \1", toml_string, flags=re.MULTILINE)

        return processed_toml

    @classmethod
    def align_equals(cls, toml_string: str) -> str:
        """
        Aligns the `=` signs in the TOML string for better readability.
        """
        lines = toml_string.splitlines()
        max_key_length = 0

        # Calculate the maximum key length for alignment
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=")[0].strip()
                max_key_length = max(max_key_length, len(key))

        # Align the `=` signs
        aligned_lines = []
        for line in lines:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                padding = " " * (max_key_length - len(key))
                aligned_lines.append(f"{key}{padding} = {value}")
            else:
                aligned_lines.append(line)

        return "\n".join(aligned_lines)

    @classmethod
    def _date_has_DST_event(cls, date: pendulum.Date, timezone: pendulum.Timezone) -> bool:
        # Convert the date to datetime at the start and end of the day
        start_of_day = pendulum.datetime(date.year, date.month, date.day, 0, 0, tz=timezone)
        end_of_day = pendulum.datetime(date.year, date.month, date.day, 23, 59, tz=timezone)

        # Get DST offset at the start and end of the day
        start_dst_offset = start_of_day.utcoffset().total_seconds()
        end_dst_offset = end_of_day.utcoffset().total_seconds()

        # If the offset changes during the day, there is a DST event
        return start_dst_offset != end_dst_offset

    @classmethod
    def _get_datetime_format(cls, date: pendulum.Date, timezone: pendulum.Timezone) -> str:
        if cls._date_has_DST_event(date, timezone):
            return "YYYY-MM-DDTHH:mmZ"
        else:
            return "YYYY-MM-DDTHH:mm"


class Workspace:

    def __init__(self):
        self.fs = FileSystem()
        self.config = Config.from_dict(tomllib.loads(self.fs.CONFIG_PATH.read_text()))

    def now(self) -> pendulum.DateTime:
        """
        Get the current time in the configured timezone
        """
        timezone = self.config.timezone
        return pendulum.now(timezone)

    def today(self) -> pendulum.Date:
        """
        Get today's date.
        """
        return pendulum.today().date()
    
    def parse_date(self, date: str) -> pendulum.Date:
        """
        Parse a date string into a pendulum.Date object.
        """
        try:
            return pendulum.parse(date).date()
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD.")

    def get_activities(self, date: pendulum.Date) -> List[Activity]:
        """
        Returns a list of activities for the given date.
        """
        plans = self.get_plans(date)
        return {activity.id: activity
                for plan in plans
                for activity in plan.activities}

    def get_plans(self, date: pendulum.Date) -> List[Plan]:
        """
        Loads all plans from the `.faff/plans` directory under the given root,
        and returns those valid on the target date.

        A plan is valid if:
        - valid_from <= target_date
        - and (valid_until >= target_date or valid_until is None)
        """
        plans = {}
        for file in self.fs.PLAN_PATH.glob("*.toml"):
            plan = Plan.from_dict(tomllib.loads(file.read_text()))

            if plan.valid_from and plan.valid_from > date:
                continue
            if plan.valid_until and plan.valid_until < date:
                continue

            if plan.source not in plans.keys():
                plans[plan.source] = plan

            if plans.get(plan.source) and plans[plan.source].valid_from < plan.valid_from:
                plans[plan.source] = plan

        return plans.values()

    def get_log(self, date: pendulum.Date) -> Log:
        """
        Returns the log for the given date.
        """
        log_path = self.fs.log_path(date)
        activities = self.get_activities(date)

        if log_path.exists():
            return Log.from_dict(tomlkit.parse(log_path.read_text()), activities)
        else:
            return Log(date, self.config.timezone)

    def write_log(self, log: Log):
        """
        Writes the log to the file.
        """
        log_contents = LogFormatter.format_log(log, self.get_activities(log.date))
        log_filename = self.fs.log_path(log.date)
        with open(log_filename, "w") as f:
            f.write(log_contents)

    def start_timeline_entry(self, activity_id: str, note: str) -> str:
        """
        Start a timeline entry for the given activity, stopping any previous one.
        """
        log = self.get_log(self.today())
        now = self.now()

        activities = self.get_activities(self.today())

        if activity_id not in activities:
            return f"Activity {activity_id} not found in today's plan."

        activity = activities[activity_id]
        log = log.start_timeline_entry(activity, now, note)

        self.write_log(log)
        return f"Started logging for activity {activity_id} at {now.to_time_string()}."

    def stop_timeline_entry(self) -> str:
        """
        Stop the most recent ongoing timeline entry.
        """
        target_date = self.today()
        log = self.get_log(target_date)
        now = self.now()

        active_entry = log.active_timeline_entry()
        if active_entry:
            self.write_log(log.stop_active_timeline_entry(now))
            return f"Stopped logging for activity {active_entry.activity.name} at {now.to_time_string()}."
        
        return "No ongoing timeline entries found to stop."

    def _plugin_instances(self, cls, configs):
        plugins = self._load_plugins()
        instances = {}

        for plugin_config in configs:
            plugin_str = plugin_config.get("plugin")
            Plugin = plugins.get(plugin_str)
            if not Plugin:
                raise ValueError(
                    f"Plugin {plugin_str} not found in configuration.")
            if not issubclass(Plugin, cls):
                raise ValueError(
                    f"Plugin {plugin_str} is not an {cls}.")
            if plugin_config.get('name') in instances.keys():
                raise ValueError(
                    f"Duplicate source name {plugin_config.get('name')} found in configuration.")
            instances[plugin_config.get('name')] = Plugin(plugin=plugin_config.get("plugin"),
                                                   name=plugin_config.get("name"),
                                                   config=plugin_config.get("config"),
                                                   state_path=self.fs.PLUGIN_STATE_PATH / slugify(plugin_config.get("name")))

        return instances

    def compilers(self):
        """
        Returns the configured compilers
        """
        # FIXME: This duplication still feels gross
        return self._plugin_instances(CompilePlugin, self.config.compilers)

    def plan_sources(self):
        """
        Returns the configured plan sources
        """
        return self._plugin_instances(PullPlugin, self.config.plan_sources)

    def write_plan(self, pull_plugin: PullPlugin, date: pendulum.Date) -> None:
        """
        Writes the plan for the given date.
        """
        plan = pull_plugin.pull_plan(date)

        path = self.fs.PLAN_PATH / pull_plugin.filename(date)

        path.write_text(TomlSerializer.serialize(plan))

    def _load_plugins(self) -> Dict[str, Type]:
        plugins = {}

        for plugin_file in self.fs.PLUGIN_PATH.glob("*.py"):
            if plugin_file.name == "__init__.py":
                continue

            module_name = f"plugins.{plugin_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and (
                    issubclass(attr, (PullPlugin, PushPlugin, CompilePlugin))
                ) and attr not in (PullPlugin, PushPlugin):
                    plugins[plugin_file.stem] = attr  # Store the class

        return plugins


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
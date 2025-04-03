import importlib
import pendulum
import re
import os
import toml
import tomllib
import subprocess

from pathlib import Path
from typing import List, Dict, Type, Any, Callable, Optional
from tomlkit import document, table, comment
from abc import ABC, abstractmethod

from faff.models import Plan, Log, Activity, TimelineEntry, SummaryEntry
from faff.context import Context

TIME_FORMAT_REGEX = re.compile(r"^\d+h(\d+m)?$|^\d+m$")

def get_log_file_path_by_date(context: Context, target_date: pendulum.Date) -> Path:
    logs_dir = context.require_faff_root() / ".faff" / "logs"
    log_file = logs_dir / f"{target_date.to_date_string()}.toml"
    return log_file

def get_log_by_date(context: Context, target_date: pendulum.Date) -> Log:
    now = pendulum.now()
    log_file = get_log_file_path_by_date(context, target_date)

    activities = valid_activities(context, target_date)

    if log_file.exists():
        with open(log_file, "r") as f:
            log = Log.from_dict(toml.load(f))
            for timelineEntry in log.timeline:
                if timelineEntry.activity.id in activities.keys():
                    timelineEntry.activity = activities.get(timelineEntry.activity.id)                
            return log
    else:
        return Log(target_date, context.config.timezone)

def date_has_DST_event(context: Context, target_date: pendulum.Date) -> bool:
    tz = context.config.timezone  # Get the timezone from the context

    # Convert the date to datetime at the start and end of the day
    start_of_day = pendulum.datetime(target_date.year, target_date.month, target_date.day, 0, 0, tz=tz)
    end_of_day = pendulum.datetime(target_date.year, target_date.month, target_date.day, 23, 59, tz=tz)

    # Get DST offset at the start and end of the day
    start_dst_offset = start_of_day.utcoffset().total_seconds()
    end_dst_offset = end_of_day.utcoffset().total_seconds()

    # If the offset changes during the day, there is a DST event
    return start_dst_offset != end_dst_offset

def get_datetime_format(context: Context, target_date: pendulum.Date) -> str:
    if date_has_DST_event(context, target_date):
        return "YYYY-MM-DDTHH:mmZ"
    else:
        return "YYYY-MM-DDTHH:mm"

def write_log(context: Context, log: Log):
    log_file = get_log_file_path_by_date(context, log.date)
    activities = valid_activities(context, log.date)

    doc = document()
    doc.add(comment("This is a Faff-format log file. See faffage.com for details."))
    doc.add(comment("It has been generated but can be edited manually."))
    doc.add(comment("Changes to rows starting with '#' will be ignored."))

    # Add log data
    doc["date"] = log.date.to_date_string()
    doc["timezone"] = str(log.timezone)

    if not date_has_DST_event(context, log.date):
        doc["--date_format"] = "YYYY-MM-DDTHH:mm"
    else:
        doc["--date_format"] = "YYYY-MM-DDTHH:mmZ"

    # Add summary entries
    summary_array = []
    for entry in log.summary:
        activity = activities.get(entry.activity.id)
        summary_entry = table()
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
    for entry in log.timeline:
        activity = activities.get(entry.activity.id)
        timeline_entry = table()
        timeline_entry["activity"] = entry.activity.id
        if activity.project:
            timeline_entry["--project"] = activity.project
        if activity.name:
            timeline_entry["--name"] = activity.name
        timeline_entry["start"] = entry.start.format(get_datetime_format(context, log.date))
        if entry.end:
            timeline_entry["end"] = entry.end.format(get_datetime_format(context, log.date))
            interval = (entry.end - entry.start)
            duration = pendulum.duration(seconds=interval.total_seconds())
            timeline_entry["--duration"] = duration.in_words() #format_duration_as_iso8601(duration)
        if entry.note:
            timeline_entry["note"] = entry.note
        timeline_array.append(timeline_entry)
    doc["timeline"] = timeline_array

    # Convert the TOML document to a string
    toml_string = doc.as_string()

    # Align the `=` signs
    processed_toml = commentify_derived_values(align_equals(toml_string))

    # Write the aligned TOML to the file
    with open(log_file, "w") as f:
        f.write(processed_toml)

def commentify_derived_values(toml_string: str) -> str:
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

def align_equals(toml_string: str) -> str:
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

def valid_activities(context: Context, target_date: pendulum.Date) -> List[str]:
    valid_plans = load_valid_plans_for_day(context, target_date)
    activities = {activity.id: activity
                  for plan in valid_plans
                  for activity in plan.activities}
    return activities

def start_timeline_entry(context: Context,
                         activity_id: str, note: str) -> str:
    """
    Start a timeline entry for the given activity, stopping any previous one.
    """
    log = get_log_by_date(context, context.today())
    now = pendulum.now()

    activities = valid_activities(context, context.today())

    if activity_id not in activities:
        return f"Activity {activity_id} not found in today's plan."

    activity = activities[activity_id]

    # Stop ongoing entries
    for timelineEntry in log.timeline:
        if not timelineEntry.end:
            timelineEntry.end = now

    log.timeline.append(TimelineEntry(activity=activity,
                                      start=pendulum.now(),
                                      note=note))

    write_log(context, log)
    return f"Started logging for activity {activity_id} at {now.to_time_string()}."

def get_active_timeline_entry(context: Context) -> Activity | None:
    """
    Report the most recent ongoing timeline entry, if there is one.
    """
    target_date = context.today()
    log = get_log_by_date(context, target_date)

    # Find the most recent ongoing timeline entry
    for timelineEntry in reversed(log.timeline):
        if not timelineEntry.end:
            return timelineEntry


def stop_timeline_entry(context: Context) -> str:
    """
    Stop the most recent ongoing timeline entry.
    """
    target_date = context.today()
    log = get_log_by_date(context, target_date)
    now = pendulum.now()

    # Find the most recent ongoing timeline entry
    for timelineEntry in reversed(log.timeline):
        if not timelineEntry.end:
            timelineEntry.end = now
            write_log(context, log)
            return f"Stopped logging for activity {timelineEntry.activity.name} at {now.to_time_string()}."

    return "No ongoing timeline entries found to stop."


def today():
    return pendulum.today().date()

def load_valid_plans_for_day(context: Context,
                             target_date: pendulum.Date) -> List[Plan]:
    """
    Loads all plans from the `.faff/plans` directory under the given root,
    and returns those valid on the target date.

    A plan is valid if:
    - valid_from <= target_date
    - and (valid_until >= target_date or valid_until is None)
    """
    plans_dir = context.require_faff_root() / ".faff" / "plans"
    valid_plans = {}
    for file in plans_dir.glob("*.toml"):
        try:
            with file.open("rb") as f:
                data = tomllib.load(f)
                plan = Plan.from_dict(data)

        except Exception as e:
            # Optionally log/print or raise depending on how strict you want to be
            continue

        if plan.valid_from and plan.valid_from > target_date:
            continue
        if plan.valid_until and plan.valid_until < target_date:
            continue

        if plan.source not in valid_plans.keys():
            valid_plans[plan.source] = plan

        if valid_plans.get(plan.source) and valid_plans[plan.source].valid_from < plan.valid_from:
            valid_plans[plan.source] = plan

    return valid_plans.values()

def edit_config(context: Context):
    config_file = context.require_faff_root() / ".faff" / "config.toml"
    editor = os.getenv("EDITOR", "vim")  # Default to vim if $EDITOR is not set

    pre_edit_hash = config_file.read_text().__hash__()
    # Open the file in the editor
    try:
        subprocess.run([editor, str(config_file)], check=True)
    except FileNotFoundError:
        return

    post_edit_hash = config_file.read_text().__hash__()

    if pre_edit_hash == post_edit_hash:
        return "No changes detected."
    else:
        return "Config updated."

def edit_log(context: Context, target_date: pendulum.Date):
    log_file = get_log_file_path_by_date(context, target_date)
    pre_edit_hash = log_file.read_text().__hash__()

    editor = os.getenv("EDITOR", "vim")  # Default to vim if $EDITOR is not set

    # Open the file in the editor
    try:
        subprocess.run([editor, str(log_file)], check=True)
    except FileNotFoundError:
        return

    post_edit_hash = log_file.read_text().__hash__()

    if pre_edit_hash == post_edit_hash:
        return "No changes detected."
    else:
        log = get_log_by_date(context, target_date)
        write_log(context, log)
        return "Log updated."

def log_is_valid(context: Context, target_date: pendulum.Date) -> List[str]:
    """Check the log data for errors and inconsistencies."""
    try:
        log = get_log_by_date(context, target_date)
        return True
    except:
        return False


def load_plugins(context: Context) -> Dict[str, Type]:
    plugins_dir = context.require_faff_root() / ".faff" / "plugins"
    plugins = {}

    if not plugins_dir.exists():
        plugins_dir.mkdir(parents=True, exist_ok=True)

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name == "__init__.py":
            continue

        module_name = f"plugins.{plugin_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and (
                issubclass(attr, PullConnector) or issubclass(attr, PushConnector)
            ) and attr not in (PullConnector, PushConnector):
                plugins[plugin_file.stem] = attr  # Store the class

    return plugins  

class PullConnector(ABC):
    @abstractmethod
    def pull_plan(self, start: pendulum.Date, end: pendulum.Date, 
                  config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetches activities for a given day.

        Args:
            config (Dict[str, Any]): Configuration specific to the source.

        Returns:
            List[Dict[str, Any]]: List of activities formatted for Faff.
        """
        pass


class PushConnector(ABC):
    @abstractmethod
    def push_timesheet(self, config: Dict[str, Any], timesheet: Dict[str, Any]) -> None:
        """
        Pushes a compiled timesheet to a remote repository.

        Args:
            config (Dict[str, Any]): Configuration specific to the destination.
            timesheet (Dict[str, Any]): The compiled timesheet to push.
        """
        pass
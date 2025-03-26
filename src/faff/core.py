import pendulum
import re
import os
import toml
import subprocess
import hashlib

from pathlib import Path
from typing import List, Callable

from faff.models import Plan

TIME_FORMAT_REGEX = re.compile(r"^\d+h(\d+m)?$|^\d+m$")


def calculate_file_hash(file_path: Path) -> str:
    """Calculate a SHA-256 hash of a file's content."""
    hash_sha256 = hashlib.sha256()
    if file_path.exists():
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def start_timeline_entry(root: Path, activity_id: str, note: str, valid_plans: List[Plan]) -> str:
    """
    Start a timeline entry for the given activity, stopping any previous one.
    """
    target_date = pendulum.today()
    logs_dir = root / ".faff" / "logs"
    log_file = logs_dir / f"{target_date.to_date_string()}.toml"
    now = pendulum.now()

    activities = {activity.id: activity for plan in valid_plans for activity in plan.activities}
    if activity_id not in activities:
        return f"Activity {activity_id} not found in today's plan."

    activity = activities[activity_id]

    if log_file.exists():
        with open(log_file, "r") as f:
            log_data = toml.load(f)
    else:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_data = {"date": target_date.to_date_string(), "entries": []}

    # Stop ongoing entries
    for entry in log_data["entries"]:
        if entry["type"] == "timeline" and "end" not in entry:
            entry["end"] = now.to_iso8601_string()
    
    # Add new entry
    log_data["entries"].append({
        "type": "timeline",
        "activity": activity_id,
        "activity_name": activity.name,
        "start": now.to_iso8601_string(),
        "notes": note
    })

    # Save the log file
    with open(log_file, "w") as f:
        toml.dump(log_data, f)

    return f"Started logging for activity {activity_id} at {now.to_time_string()}."

def stop_timeline_entry(root: Path) -> str:
    """
    Stop the most recent ongoing timeline entry.
    """
    target_date = pendulum.today()
    logs_dir = root / ".faff" / "logs"
    log_file = logs_dir / f"{target_date.to_date_string()}.toml"
    now = pendulum.now()

    if not log_file.exists():
        return "No log file found for today. Nothing to stop."

    # Load the log file
    with open(log_file, "r") as f:
        log_data = toml.load(f)

    # Find the most recent ongoing timeline entry
    for entry in reversed(log_data["entries"]):
        if entry["type"] == "timeline" and "end" not in entry:
            entry["end"] = now.to_iso8601_string()
            with open(log_file, "w") as f:
                toml.dump(log_data, f)
            return f"Stopped logging for activity {entry['activity']} at {now.to_time_string()}."

    return "No ongoing timeline entries found to stop."


def today():
    return pendulum.today().date()

def load_valid_plans_for_day(root: Path, target_date: pendulum.Date) -> List[Plan]:
    """
    Loads all plans from the `.faff/plans` directory under the given root,
    and returns those valid on the target date.

    A plan is valid if:
    - valid_from <= target_date
    - and (valid_until >= target_date or valid_until is None)
    """
    plans_dir = root / ".faff" / "plans"
    valid_plans = {}
    for file in plans_dir.glob("*.toml"):
        try:
            plan = Plan.from_toml_file(file)
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


def log_end_of_day_editor(root: Path,
                          valid_plans: List[Plan],
                          target_date: pendulum.Date,
                          reporter: Callable[[str], None] = print):
    """
    Prepare a log file for the day and open it in the user's preferred editor.
    """
    logs_dir = root / ".faff" / "logs"
    log_file = logs_dir / f"{target_date.to_date_string()}.toml"
    
    # Create log file if it doesn't exist
    if not log_file.exists():
        log_data = {"date": target_date.to_date_string(),
                    "timezone": pendulum.now().timezone.name, # FIXME: This should be driven by config that defaults to the system timezone
                    "entries": []}
        
        activities = {activity.id: activity for plan in valid_plans for activity in plan.activities}
        
        if not activities:
            reporter("No valid activities found for today. Aborting.")
            return
    # Create log file if it doesn't exist
    if not log_file.exists():
        log_data = {"date": target_date.to_date_string(), "entries": []}
        
        activities = {activity.id: activity for plan in valid_plans for activity in plan.activities}
        
        if not activities:
            reporter("No valid activities found for today. Aborting.")
            return
        
        # Prepare file content with comments
        lines = [
            "# Fill in the time spent on each activity, e.g., '1h', '30m', '2h15m'",
            "# You can also leave notes if needed.",
            f"# Log for {target_date.to_date_string()}\n",
            "date = \"{}\"\n".format(target_date.to_date_string())
        ]

        for activity_id, activity in activities.items():
            lines.append(f"\n# Activity: {activity.name}")
            if activity.metadata:
                for key, value in activity.metadata.items():
                    lines.append(f"# {key}: {value}")
            
            # Prepopulate with placeholder entry
            lines.append(f"[[entries]]")
            lines.append(f"activity = \"{activity_id}\"")
            lines.append(f"type = \"summary\"")
            lines.append("time_spent = \"\"")
            lines.append("notes = \"\"")
        
        # Write to the file
        with open(log_file, "w") as f:
            f.write("\n".join(lines))

    original_hash = calculate_file_hash(log_file)

    # Detect the user's preferred editor
    editor = os.getenv("EDITOR", "vim")  # Default to vim if $EDITOR is not set

    # Open the file in the editor
    try:
        subprocess.run([editor, str(log_file)], check=True)
    except FileNotFoundError:
        reporter(f"Could not open the editor {editor}. Please make sure it is installed.")
        return

    updated_hash = calculate_file_hash(log_file)

    if original_hash == updated_hash:
        reporter("No changes were made. The log file has not been modified.")
        return

    # Now, let's read back the file and validate it
    with open(log_file, "r") as f:
        try:
            log_data = toml.load(f)
        except toml.TomlDecodeError as e:
            reporter(f"Failed to parse the log file. Error: {str(e)}")
            return

    validation_errors = validate_log(log_data, valid_plans)
    if validation_errors:
        for error in validation_errors:
            reporter(f"Error: {error}")
        reporter("Please fix the above errors and try again.")
    else:
        reporter(f"Log saved successfully to {log_file}")


def validate_log(log_data: dict, valid_plans: List[Plan]) -> List[str]:
    """Check the log data for errors and inconsistencies."""
    errors = []
    valid_activity_ids = {activity.id for plan in valid_plans for activity in plan.activities}
    
    # Check date field
    if "date" not in log_data:
        errors.append("Missing 'date' field in the log file.")
    else:
        try:
            pendulum.parse(log_data["date"]).date()
        except ValueError:
            errors.append(f"Invalid date format: {log_data['date']}")
    
    # Check entries
    if "entries" not in log_data or not isinstance(log_data["entries"], list):
        errors.append("Missing or malformed 'entries' section.")
        return errors
    
    for entry in log_data["entries"]:
        if "activity" not in entry:
            errors.append("An entry is missing the 'activity' field.")
            continue
        
        activity_id = entry["activity"]
        
        if activity_id not in valid_activity_ids:
            errors.append(f"Unknown activity ID: {activity_id}")
        
        # Check if time_spent is valid
        # FIXME: there isn't always a time_spent field
        # if entry["time_spent"] and not TIME_FORMAT_REGEX.match(entry["time_spent"]):
        #     errors.append(f"Invalid time format for activity {activity_id}: {entry['time_spent']}")
        
    return errors
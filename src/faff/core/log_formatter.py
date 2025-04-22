from faff.models import Activity, Log


import pendulum
import tomlkit


import re
from typing import List


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
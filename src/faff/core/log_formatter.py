from faff.models import Activity, Log

import pendulum

import re
from typing import List

class LogFormatter:

    @classmethod
    def format_log(cls, log: Log, activities: List[Activity]) -> str:
        formatted_log = []
        formatted_log.append("# This is a Faff-format log file - see faffage.com for details.")
        formatted_log.append("# It has been generated but can be edited manually.")
        formatted_log.append("# Changes to rows starting with '#' will not be saved.")

        # Add log data
        formatted_log.append("version = \"1.0\"")
        formatted_log.append(f'date = "{ log.date.to_date_string()}"')
        formatted_log.append(f'timezone = "{str(log.timezone)}"')

        formatted_log.append(f'--date_format = "{cls._get_datetime_format(log.date, log.timezone)}"')

        # FIXME: Summaries are not addressed here at all

        # Add summary entries
        for entry in sorted(log.timeline, key=lambda entry: entry.start):
            activity = activities.get(entry.activity.id)
            formatted_log.append("")
            formatted_log.append("[[timeline]]")
            formatted_log.append(f'activity = "{entry.activity.id}"')
            if activity.name:
                formatted_log.append(f'--name = "{activity.name}"')

            formatted_log.append(f'start = "{entry.start.format(cls._get_datetime_format(log.date, log.timezone))}"')
            if entry.end:
                formatted_log.append(f'end = "{entry.end.format(cls._get_datetime_format(log.date, log.timezone))}"')
                interval = (entry.end - entry.start)
                duration = pendulum.duration(seconds=interval.total_seconds())
                formatted_log.append(f'--duration = "{duration.in_words()}"')
            if entry.note:
                formatted_log.append(f'note = "{entry.note}"')

        if len(log.timeline) == 0:
            formatted_log.append("")
            formatted_log.append("# Timeline is empty.")

        toml_string = "\n".join(formatted_log)

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
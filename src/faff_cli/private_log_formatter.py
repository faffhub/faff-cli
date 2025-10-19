from faff_core.models import Log

import humanize
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

import re

class PrivateLogFormatter:

    @classmethod
    def format_log(cls, log: Log, trackers: dict[str, str]) -> str:
        formatted_log = []
        formatted_log.append("# This is a Faff-format log file - see faffage.com for details.")
        formatted_log.append("# It has been generated but can be edited manually.")
        formatted_log.append("# Changes to rows starting with '#' will not be saved.")

        # Add log data
        formatted_log.append("version = \"1.1\"")
        formatted_log.append(f'date = "{ log.date.isoformat()}"')
        formatted_log.append(f'timezone = "{str(log.timezone)}"')

        formatted_log.append(f'--date_format = "{cls._get_datetime_format(log.date, log.timezone)}"')

        # FIXME: Summaries are not addressed here at all

        # Add summary entries
        for entry in sorted(log.timeline, key=lambda entry: entry.start):
            formatted_log.append("")
            formatted_log.append("[[timeline]]")

            formatted_log.append(f'alias = "{entry.intent.alias}"')
            if entry.intent.role:
                formatted_log.append(f'role = "{entry.intent.role}"')
            if entry.intent.objective:
                formatted_log.append(f'objective = "{entry.intent.objective}"')
            if entry.intent.action:
                formatted_log.append(f'action = "{entry.intent.action}"')
            if entry.intent.subject:
                formatted_log.append(f'subject = "{entry.intent.subject}"')


            if entry.intent.trackers:
                if len(entry.intent.trackers) == 1:
                    tracker = entry.intent.trackers[0]
                    name: str | None = trackers.get(tracker)
                    if name:
                        formatted_log.append(f'trackers = "{tracker}" # {name}')
                    else:
                        formatted_log.append(f'trackers = "{tracker}"')
                else:
                    formatted_log.append("trackers = [")
                    for tracker in entry.intent.trackers:
                        name = trackers.get(tracker)
                        if name:
                            formatted_log.append(f'   "{tracker}", # {name}')
                        else:
                            formatted_log.append(f'   "{tracker}",')
                    formatted_log.append("]")

            formatted_log.append(f'start = "{entry.start.strftime(cls._get_datetime_format(log.date, log.timezone).replace("HH", "%H").replace("mm", "%M").replace("Z", "%z"))}"')
            if entry.end:
                formatted_log.append(f'end = "{entry.end.strftime(cls._get_datetime_format(log.date, log.timezone).replace("HH", "%H").replace("mm", "%M").replace("Z", "%z"))}"')
                interval = (entry.end - entry.start)
                duration = humanize.precisedelta(interval)
                formatted_log.append(f'--duration = "{duration}"')
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
        pattern = r"^--([a-zA-Z_-][a-zA-Z0-9_-]*\s*=\s*.+)$"

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
    def _date_has_DST_event(cls, date: date, timezone: ZoneInfo) -> bool:
        start = datetime.combine(date, time(0, 0), tzinfo=timezone)
        end = datetime.combine(date, time(23, 59), tzinfo=timezone)
        
        return start.utcoffset() != end.utcoffset()

    @classmethod
    def _get_datetime_format(cls, date: date, timezone: ZoneInfo) -> str:
        if cls._date_has_DST_event(date, timezone):
            return "HH:mmZ"
        else:
            return "HH:mm"
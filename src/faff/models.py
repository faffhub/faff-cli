from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
import pendulum

"""
FIXME: Everything in here should just be models - not utility functions for formatting or
reading/writing to disk.
"""

@dataclass
class Activity:
    """An activity you can log time against."""
    id: str  # Globally unique identifier, e.g., "project:feature" or UUID
    name: str  # Human-readable label
    project: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)  # Optional extra info

@dataclass
class Plan:
    """A collection of activities valid for a period of time."""
    source: str  # e.g. 'local', 'https://example.com/plan'
    valid_from: pendulum.Date
    valid_until: Optional[pendulum.Date] = None
    activities: List[Activity] = field(default_factory=list)

    @staticmethod
    def from_toml_file(path: Path) -> Plan:
        import tomllib
        with path.open("rb") as f:
            data = tomllib.load(f)

        activities = [Activity(**a) for a in data["activities"]]
        return Plan(
            source=data["source"],
            valid_from=pendulum.parse(data["valid_from"]).date(),
            valid_until=pendulum.parse(data["valid_until"]).date() if "valid_until" in data else None,
            activities=activities
        )


@dataclass
class Log:
    """A record of time spent on activities."""
    date: pendulum.Date
    timezone: pendulum.Timezone
    summary: List[SummaryEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)

    @staticmethod
    def from_toml(toml_data: dict) -> Log:
        date = pendulum.parse(toml_data["date"]).date()
        timezone = pendulum.timezone(toml_data["timezone"])
        summary = [SummaryEntry.from_toml(e) for e in toml_data.get("summary", [])]
        timeline = [TimelineEntry.from_toml(e) for e in toml_data.get("timeline", [])]
        return Log(date, timezone, summary, timeline)


@dataclass
class TimelineEntry:
    """A record of time spent on an activity."""
    activity: Activity
    start: pendulum.DateTime
    end: Optional[pendulum.DateTime] = None
    note: Optional[str] = None

    @staticmethod
    def from_toml(toml_data: dict) -> TimelineEntry:
        activity = Activity(id = toml_data.get("activity"),
                            name = toml_data.get("name"),
                            meta = toml_data.get("meta", {}))
        start = pendulum.parse(toml_data["start"])
        end = pendulum.parse(toml_data["end"]) if "end" in toml_data else None
        return TimelineEntry(activity, start, end, toml_data.get("note"))

    def stop(self, stop_time: pendulum.DateTime) -> TimelineEntry:
        return TimelineEntry(
            activity=self.activity,
            start=self.start,
            project=self.project,
            end=stop_time,
            note=self.note,
            meta=self.meta
        )
    

@dataclass
class SummaryEntry:
    """A record of a total number of hours spent on an activity."""
    activity: Activity
    duration: str # ISO8601 duration string
    note: Optional[str] = None

    @staticmethod
    def from_toml(toml_data: dict) -> TimelineEntry:
        activity = Activity(id = toml_data.get("activity"),
                            name = toml_data.get("name"),
                            meta = toml_data.get("meta", {}))
        return SummaryEntry(activity, toml_data["duration"], toml_data.get("note"))
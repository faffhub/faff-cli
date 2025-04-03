from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

import pendulum

"""
This module defines the data models.
These models should have methods to hydrate themselves from dicts, and to serialize themselves to dicts.
At this stage, I see no reason why the model objects shouldn't be immutable, so to begin with 
they will be. Methods to stop and start activities will return new objects with the updated state.
"""

@dataclass(frozen=True)
class Activity:
    """An activity you can log time against."""
    id: str  # Globally unique identifier, e.g., "project:feature" or UUID
    name: str  # Human-readable label
    project: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)  # Optional extra info

    @classmethod
    def from_dict(cls, data: dict) -> Activity:
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            project=data.get("project"),
            meta=data.get("meta", {})
        )

@dataclass(frozen=True)
class Plan:
    """A collection of activities valid for a period of time."""
    source: str  # e.g. 'local', 'https://example.com/plan'
    valid_from: pendulum.Date
    valid_until: Optional[pendulum.Date] = None
    activities: List[Activity] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        activities = [Activity.from_dict(a) for a in data.get("activities", [])]
        return cls(
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

    @classmethod
    def from_dict(cls, data: dict) -> Log:
        date = pendulum.parse(data["date"]).date()
        timezone = pendulum.timezone(data["timezone"])
        summary = [SummaryEntry.from_toml(e) for e in data.get("summary", [])]
        timeline = [TimelineEntry.from_toml(e) for e in data.get("timeline", [])]
        return cls(date, timezone, summary, timeline)

@dataclass(frozen=True)
class TimelineEntry:
    """A record of time spent on an activity."""
    activity: Activity
    start: pendulum.DateTime
    end: Optional[pendulum.DateTime] = None
    note: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> TimelineEntry:
        activity = Activity(id = data.get("activity"),
                            name = data.get("name"),
                            meta = data.get("meta", {}))
        start = pendulum.parse(data["start"])
        end = pendulum.parse(data["end"]) if "end" in data else None
        return cls(activity, start, end, data.get("note"))

    @classmethod
    def stop(cls, self, stop_time: pendulum.DateTime) -> TimelineEntry:
        return cls(
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

    @classmethod
    def from_dict(cls, toml_data: dict) -> TimelineEntry:
        activity = Activity(id = toml_data.get("activity"),
                            name = toml_data.get("name"),
                            meta = toml_data.get("meta", {}))
        return cls(activity, toml_data["duration"], toml_data.get("note"))
    
@dataclass
class Config:
    """Configuration for the faff CLI. This object includes the default values for the CLI."""
    timezone: pendulum.Timezone = pendulum.now().timezone
    plan_sources: List[Dict[str, Any]] = field(default_factory=list)
    push_targets: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        if "timezone" in data:
            timezone = pendulum.timezone(data.get("timezone"))
        else:
            timezone = pendulum.now().timezone
        plan_sources = data.get("plan_source", [])
        push_targets = data.get("push_target", [])
        return cls(timezone, plan_sources, push_targets)
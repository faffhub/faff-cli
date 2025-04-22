from __future__ import annotations

from dataclasses import dataclass, field 
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



@dataclass(frozen=True)
class TimelineEntry:
    """A record of time spent on an activity."""
    activity: Activity
    start: pendulum.DateTime
    end: Optional[pendulum.DateTime] = None
    note: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict, activities: Dict[str, Activity], timezone: pendulum.Timezone) -> TimelineEntry:
        # XXX: I think I prefer that the log only persists the activity ID,
        # but that could have unintended consequences.
        # activity = Activity(id = data.get("activity"),
        #                     name = data.get("name"),
        #                     meta = data.get("meta", {}))
        activity = activities.get(data.get("activity"))
        start = pendulum.parse(data["start"], tz=timezone)
        end = pendulum.parse(data["end"], tz=timezone) if "end" in data else None
        return cls(activity, start, end, data.get("note"))

    def stop(self, stop_time: pendulum.DateTime) -> TimelineEntry:
        return TimelineEntry(
            activity=self.activity,
            start=self.start,
            end=stop_time,
            note=self.note
        )

@dataclass(frozen=True)
class SummaryEntry:
    """A record of a total number of hours spent on an activity."""
    activity: Activity
    duration: str # ISO8601 duration string
    note: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict, activities: Dict[str, Activity]) -> TimelineEntry:
        # XXX: I think I prefer that the log only persists the activity ID,
        # but that could have unintended consequences.
        # activity = Activity(id = data.get("activity"),
        #                     name = data.get("name"),
        #                     meta = data.get("meta", {}))
        activity = activities.get(data.get("activity"))

        activity = Activity(id = data.get("activity"),
                            name = data.get("name"),
                            meta = data.get("meta", {}))
        return cls(activity, data["duration"], data.get("note"))

@dataclass(frozen=True)
class Log:
    """A record of time spent on activities."""
    date: pendulum.Date
    timezone: pendulum.Timezone
    summary: List[SummaryEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, activities: Dict[str, Activity]) -> Log:
        date = pendulum.parse(data["date"]).date()
        timezone = pendulum.timezone(data["timezone"])
        summary = [SummaryEntry.from_dict(e, activities) for e in data.get("summary", [])]
        timeline = [TimelineEntry.from_dict(e, activities, timezone) for e in data.get("timeline", [])]
        return cls(date, timezone, summary, timeline)
    
    def start_timeline_entry(self, activity: Activity, start: pendulum.DateTime,
                                note: Optional[str] = None) -> Log:
        
        if self.active_timeline_entry():
            stopped_log = self.stop_active_timeline_entry(start)
            return stopped_log.start_timeline_entry(activity, start, note)
        else:
            return Log(
                date=self.date,
                timezone=self.timezone,
                summary=self.summary,
                timeline=self.timeline + [TimelineEntry(activity, start, end=None, note=note)]
            )
    
    def active_timeline_entry(self) -> Optional[TimelineEntry]:
        if not self.timeline:
            return None
        latest_entry = self.timeline[-1]
        if latest_entry.end is None:
            return latest_entry
        return None

    def stop_active_timeline_entry(self, stop_time: pendulum.DateTime) -> Log:
        if not self.timeline:
            raise ValueError("No timeline entries to stop.")
        latest_entry = self.timeline[-1]
        stopped_entry = latest_entry.stop(stop_time)
        return Log(
            date=self.date,
            timezone=self.timezone,
            summary=self.summary,
            timeline=self.timeline[:-1] + [stopped_entry]
        )

@dataclass(frozen=True)
class TimeSheet():
    """A filtered business."""
    subject: Dict[str, Any]
    signatures: List[str]
    date: pendulum.Date
    timezone: pendulum.Timezone
    summary: List[SummaryEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)

@dataclass
class Config:
    """Configuration for the faff CLI. This object includes the default values for the CLI."""
    timezone: pendulum.Timezone = pendulum.now().timezone
    plan_sources: List[Dict[str, Any]] = field(default_factory=list)
    compilers: List[Dict[str, Any]] = field(default_factory=list)
    push_targets: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        if "timezone" in data:
            timezone = pendulum.timezone(data.get("timezone"))
        else:
            timezone = pendulum.now().timezone
        plan_sources = data.get("plan_source", [])
        compilers = data.get("compiler", [])
        push_targets = data.get("push_target", [])
        return cls(timezone, plan_sources, compilers, push_targets)
    

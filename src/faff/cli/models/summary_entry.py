from __future__ import annotations

from .activity import Activity
from .timeline_entry import TimelineEntry

from dataclasses import dataclass
from typing import Dict, Optional


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
from __future__ import annotations

from faff.models import Activity

from typing import Optional

import pendulum

from dataclasses import dataclass
from typing import Dict

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
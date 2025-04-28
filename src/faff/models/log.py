from __future__ import annotations

from faff.models import Activity, SummaryEntry, TimelineEntry

import pendulum

from dataclasses import dataclass, field
from typing import Dict, List, Optional

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

    def total_recorded_time(self) -> pendulum.Duration:
        total_recorded_time = pendulum.duration(0)
        for entry in self.timeline:
            if entry.end is None:
                duration = pendulum.now(self.timezone) - entry.start
            else:
                duration = entry.end - entry.start

            total_recorded_time += duration

        return total_recorded_time
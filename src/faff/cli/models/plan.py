from __future__ import annotations

from .activity import Activity

import pendulum

from dataclasses import dataclass, field
from typing import List, Optional

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
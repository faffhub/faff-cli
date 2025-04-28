from __future__ import annotations

from faff.models import SummaryEntry, TimelineEntry

import pendulum

from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass(frozen=True)
class Timesheet():
    """A filtered business."""
    subject: Dict[str, Any]
    signatures: List[str]
    date: pendulum.Date
    timezone: pendulum.Timezone
    summary: List[SummaryEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)
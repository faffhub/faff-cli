from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
import pendulum


@dataclass
class Activity:
    """An activity you can log time against."""
    id: str  # Globally unique identifier, e.g., "project:feature" or UUID
    name: str  # Human-readable label
    metadata: Dict[str, str] = field(default_factory=dict)  # Optional extra info


@dataclass
class Plan:
    """A collection of activities valid for a period of time."""
    source: str  # e.g. 'local', 'https://example.com/plan'
    valid_from: pendulum.Date
    valid_until: Optional[pendulum.Date] = None
    activities: List[Activity] = field(default_factory=list)

    @staticmethod
    def from_toml_file(path: Path) -> "Plan":
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

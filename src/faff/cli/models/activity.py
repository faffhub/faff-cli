from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

@dataclass(frozen=True)
class Activity:
    """An activity you can log time against."""
    id: str  # Globally unique identifier, e.g., "project:feature" or UUID
    name: str  # Human-readable label
    meta: Dict[str, str] = field(default_factory=dict)  # Optional extra info

    @classmethod
    def from_dict(cls, data: dict) -> Activity:
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            meta=data.get("meta", {})
        )
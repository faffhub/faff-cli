from __future__ import annotations

import pendulum

from dataclasses import dataclass, field
from typing import Any, Dict, List

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
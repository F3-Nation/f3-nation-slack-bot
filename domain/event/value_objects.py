from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

# NOTE: event aggregate can reference org EventTypeId/EventTagId when needed;
# import locally in modules that need them to avoid unused import warnings.

EventSeriesId = NewType("EventSeriesId", int)
EventInstanceId = NewType("EventInstanceId", int)


@dataclass(frozen=True)
class EventName:
    value: str

    def __post_init__(self):
        v = (self.value or "").strip()
        if not v:
            raise ValueError("Event name cannot be empty")
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class TimeHHMM:
    value: str | None

    def __post_init__(self):
        v = (self.value or "").strip()
        if not v:
            object.__setattr__(self, "value", None)
            return
        if len(v) != 4 or not v.isdigit():
            raise ValueError("Time must be HHMM")
        hh, mm = int(v[:2]), int(v[2:])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("Time must be HHMM")
        object.__setattr__(self, "value", v)

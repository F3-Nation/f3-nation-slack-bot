from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

OrgId = NewType("OrgId", int)
UserId = NewType("UserId", int)
RoleId = NewType("RoleId", int)
EventTypeId = NewType("EventTypeId", int)
EventTagId = NewType("EventTagId", int)
LocationId = NewType("LocationId", int)
PositionId = NewType("PositionId", int)


@dataclass(frozen=True)
class EventTypeName:
    value: str

    def __post_init__(self):
        v = (self.value or "").strip()
        if not v:
            raise ValueError("Event type name cannot be empty")
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class EventTagName:
    value: str

    def __post_init__(self):
        v = (self.value or "").strip()
        if not v:
            raise ValueError("Event tag name cannot be empty")
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class Acronym:
    value: str

    def __post_init__(self):
        v = (self.value or "").strip().upper()
        if not v or len(v) > 2:
            raise ValueError("Acronym must be 1-2 characters")
        object.__setattr__(self, "value", v)


@dataclass(frozen=True)
class PositionName:
    value: str

    def __post_init__(self):
        v = (self.value or "").strip()
        if not v:
            raise ValueError("Position name cannot be empty")
        object.__setattr__(self, "value", v)

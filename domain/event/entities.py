from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Set

from domain.org.value_objects import EventTagId, EventTypeId, OrgId, UserId

from .events import (
    EventInstanceCreated,
    EventInstanceDeactivated,
    EventInstanceUpdated,
    EventSeriesCreated,
    EventSeriesDeactivated,
    EventSeriesUpdated,
)
from .value_objects import EventInstanceId, EventName, EventSeriesId, TimeHHMM


class _IdSeq:
    def __init__(self):
        self._v = 0

    def next(self):
        self._v += 1
        return self._v


_series_seq = _IdSeq()
_instance_seq = _IdSeq()


@dataclass
class EventSeries:
    id: EventSeriesId
    org_id: OrgId
    name: EventName
    description: Optional[str] = None
    location_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[TimeHHMM] = None
    end_time: Optional[TimeHHMM] = None
    day_of_week: Optional[int] = None  # 0-6
    recurrence_pattern: Optional[str] = None  # weekly|monthly
    recurrence_interval: Optional[int] = None
    index_within_interval: Optional[int] = None
    is_active: bool = True
    event_type_ids: Set[EventTypeId] = field(default_factory=set)
    event_tag_ids: Set[EventTagId] = field(default_factory=set)
    _events: list = field(default_factory=list, init=False)

    @staticmethod
    def create(org_id: OrgId, name: str, *, triggered_by: Optional[UserId] = None, **kwargs) -> "EventSeries":
        s = EventSeries(
            id=EventSeriesId(_series_seq.next()),
            org_id=org_id,
            name=EventName(name),
            description=kwargs.get("description"),
            location_id=kwargs.get("location_id"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            start_time=TimeHHMM(kwargs.get("start_time")),
            end_time=TimeHHMM(kwargs.get("end_time")),
            day_of_week=kwargs.get("day_of_week"),
            recurrence_pattern=kwargs.get("recurrence_pattern"),
            recurrence_interval=kwargs.get("recurrence_interval"),
            index_within_interval=kwargs.get("index_within_interval"),
        )
        s.record(EventSeriesCreated.create(org_id, s.id, s.name.value, triggered_by))
        return s

    def record(self, event):
        self._events.append(event)

    @property
    def events(self):
        return list(self._events)

    def update_profile(self, *, name: Optional[str] = None, triggered_by: Optional[UserId] = None, **kwargs):
        changes = {}
        if name is not None:
            self.name = EventName(name)
            changes["name"] = self.name.value
        for f in [
            "description",
            "location_id",
            "start_date",
            "end_date",
            "day_of_week",
            "recurrence_pattern",
            "recurrence_interval",
            "index_within_interval",
        ]:
            if f in kwargs:
                setattr(self, f, kwargs[f])
                changes[f] = kwargs[f]
        if "start_time" in kwargs:
            self.start_time = TimeHHMM(kwargs["start_time"]) if kwargs["start_time"] else None
            changes["start_time"] = self.start_time.value if self.start_time else None
        if "end_time" in kwargs:
            self.end_time = TimeHHMM(kwargs["end_time"]) if kwargs["end_time"] else None
            changes["end_time"] = self.end_time.value if self.end_time else None
        if changes:
            self.record(EventSeriesUpdated.create(self.org_id, self.id, changes, triggered_by))

    def deactivate(self, *, triggered_by: Optional[UserId] = None):
        if not self.is_active:
            return
        self.is_active = False
        self.record(EventSeriesDeactivated.create(self.org_id, self.id, triggered_by))


@dataclass
class EventInstance:
    id: EventInstanceId
    org_id: OrgId
    name: EventName
    date: date
    description: Optional[str] = None
    location_id: Optional[int] = None
    series_id: Optional[EventSeriesId] = None
    start_time: Optional[TimeHHMM] = None
    end_time: Optional[TimeHHMM] = None
    is_active: bool = True
    event_type_ids: Set[EventTypeId] = field(default_factory=set)
    event_tag_ids: Set[EventTagId] = field(default_factory=set)
    _events: list = field(default_factory=list, init=False)

    @staticmethod
    def create(
        org_id: OrgId,
        name: str,
        date: date,
        *,
        series_id: Optional[EventSeriesId] = None,
        triggered_by: Optional[UserId] = None,
        **kwargs,
    ) -> "EventInstance":
        inst = EventInstance(
            id=EventInstanceId(_instance_seq.next()),
            org_id=org_id,
            name=EventName(name),
            date=date,
            description=kwargs.get("description"),
            location_id=kwargs.get("location_id"),
            series_id=series_id,
            start_time=TimeHHMM(kwargs.get("start_time")),
            end_time=TimeHHMM(kwargs.get("end_time")),
        )
        inst.record(EventInstanceCreated.create(org_id, inst.id, inst.name.value, triggered_by))
        return inst

    def record(self, event):
        self._events.append(event)

    @property
    def events(self):
        return list(self._events)

    def update_profile(self, *, name: Optional[str] = None, triggered_by: Optional[UserId] = None, **kwargs):
        changes = {}
        if name is not None:
            self.name = EventName(name)
            changes["name"] = self.name.value
        for f in ["description", "location_id", "date"]:
            if f in kwargs:
                setattr(self, f, kwargs[f])
                changes[f] = kwargs[f]
        if "start_time" in kwargs:
            self.start_time = TimeHHMM(kwargs["start_time"]) if kwargs["start_time"] else None
            changes["start_time"] = self.start_time.value if self.start_time else None
        if "end_time" in kwargs:
            self.end_time = TimeHHMM(kwargs["end_time"]) if kwargs["end_time"] else None
            changes["end_time"] = self.end_time.value if self.end_time else None
        if changes:
            self.record(EventInstanceUpdated.create(self.org_id, self.id, changes, triggered_by))

    def deactivate(self, *, triggered_by: Optional[UserId] = None):
        if not self.is_active:
            return
        self.is_active = False
        self.record(EventInstanceDeactivated.create(self.org_id, self.id, triggered_by))

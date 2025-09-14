from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.org.value_objects import OrgId, UserId

from .value_objects import EventInstanceId, EventSeriesId


@dataclass(frozen=True)
class EventSeriesCreated:
    org_id: OrgId
    series_id: EventSeriesId
    name: str
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, series_id: EventSeriesId, name: str, triggered_by: Optional[UserId]):
        return EventSeriesCreated(org_id, series_id, name, triggered_by)


@dataclass(frozen=True)
class EventSeriesUpdated:
    org_id: OrgId
    series_id: EventSeriesId
    changes: dict
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, series_id: EventSeriesId, changes: dict, triggered_by: Optional[UserId]):
        return EventSeriesUpdated(org_id, series_id, changes, triggered_by)


@dataclass(frozen=True)
class EventSeriesDeactivated:
    org_id: OrgId
    series_id: EventSeriesId
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, series_id: EventSeriesId, triggered_by: Optional[UserId]):
        return EventSeriesDeactivated(org_id, series_id, triggered_by)


@dataclass(frozen=True)
class EventInstanceCreated:
    org_id: OrgId
    instance_id: EventInstanceId
    name: str
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, instance_id: EventInstanceId, name: str, triggered_by: Optional[UserId]):
        return EventInstanceCreated(org_id, instance_id, name, triggered_by)


@dataclass(frozen=True)
class EventInstanceUpdated:
    org_id: OrgId
    instance_id: EventInstanceId
    changes: dict
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, instance_id: EventInstanceId, changes: dict, triggered_by: Optional[UserId]):
        return EventInstanceUpdated(org_id, instance_id, changes, triggered_by)


@dataclass(frozen=True)
class EventInstanceDeactivated:
    org_id: OrgId
    instance_id: EventInstanceId
    triggered_by: Optional[UserId]

    @staticmethod
    def create(org_id: OrgId, instance_id: EventInstanceId, triggered_by: Optional[UserId]):
        return EventInstanceDeactivated(org_id, instance_id, triggered_by)

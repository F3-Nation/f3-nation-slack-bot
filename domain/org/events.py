from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .value_objects import EventTagId, EventTypeId, LocationId, OrgId, UserId


def _ts() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DomainEvent:
    org_id: OrgId
    occurred_at: datetime
    triggered_by: Optional[UserId]
    name: str
    payload: Dict[str, Any]


# Concrete events
@dataclass
class EventTypeCreated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_type_id: EventTypeId, name: str, acronym: str, triggered_by: Optional[UserId]):
        return EventTypeCreated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTypeCreated",
            payload={"event_type_id": event_type_id, "name": name, "acronym": acronym},
        )


@dataclass
class EventTypeUpdated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_type_id: EventTypeId, fields: Dict[str, Any], triggered_by: Optional[UserId]):
        return EventTypeUpdated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTypeUpdated",
            payload={"event_type_id": event_type_id, "fields": fields},
        )


@dataclass
class EventTypeDeleted(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_type_id: EventTypeId, triggered_by: Optional[UserId]):
        return EventTypeDeleted(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTypeDeleted",
            payload={"event_type_id": event_type_id},
        )


@dataclass
class EventTagCreated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_tag_id: EventTagId, name: str, color: str, triggered_by: Optional[UserId]):
        return EventTagCreated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTagCreated",
            payload={"event_tag_id": event_tag_id, "name": name, "color": color},
        )


@dataclass
class EventTagUpdated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_tag_id: EventTagId, fields: Dict[str, Any], triggered_by: Optional[UserId]):
        return EventTagUpdated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTagUpdated",
            payload={"event_tag_id": event_tag_id, "fields": fields},
        )


@dataclass
class EventTagDeleted(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, event_tag_id: EventTagId, triggered_by: Optional[UserId]):
        return EventTagDeleted(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="EventTagDeleted",
            payload={"event_tag_id": event_tag_id},
        )


# Location events
@dataclass
class LocationCreated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, location_id: LocationId, name: str, triggered_by: Optional[UserId]):
        return LocationCreated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="LocationCreated",
            payload={"location_id": location_id, "name": name},
        )


@dataclass
class LocationUpdated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, location_id: LocationId, fields: Dict[str, Any], triggered_by: Optional[UserId]):
        return LocationUpdated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="LocationUpdated",
            payload={"location_id": location_id, "fields": fields},
        )


@dataclass
class LocationDeleted(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, location_id: LocationId, triggered_by: Optional[UserId]):
        return LocationDeleted(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="LocationDeleted",
            payload={"location_id": location_id},
        )

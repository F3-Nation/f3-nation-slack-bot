from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .value_objects import EventTagId, EventTypeId, LocationId, OrgId, PositionId, UserId


def _ts() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DomainEvent:
    org_id: OrgId
    occurred_at: datetime
    triggered_by: Optional[UserId]
    name: str
    payload: Dict[str, Any]


# Org profile events
@dataclass
class OrgProfileUpdated(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, fields: Dict[str, Any], triggered_by: Optional[UserId]):
        return OrgProfileUpdated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="OrgProfileUpdated",
            payload={"fields": dict(fields or {})},
        )


# Admin events
@dataclass
class OrgAdminAssigned(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, user_id: UserId, triggered_by: Optional[UserId]):
        return OrgAdminAssigned(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="OrgAdminAssigned",
            payload={"user_id": user_id},
        )


@dataclass
class OrgAdminRevoked(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, user_id: UserId, triggered_by: Optional[UserId]):
        return OrgAdminRevoked(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="OrgAdminRevoked",
            payload={"user_id": user_id},
        )


@dataclass
class OrgAdminsReplaced(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, user_ids: list[UserId], triggered_by: Optional[UserId]):
        return OrgAdminsReplaced(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="OrgAdminsReplaced",
            payload={"user_ids": list(user_ids or [])},
        )


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


# Position events
@dataclass
class PositionCreated(DomainEvent):
    @staticmethod
    def create(
        org_id: OrgId,
        position_id: PositionId,
        name: str,
        org_type: Optional[str],
        triggered_by: Optional[UserId],
    ):
        return PositionCreated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="PositionCreated",
            payload={"position_id": position_id, "name": name, "org_type": org_type},
        )


@dataclass
class PositionUpdated(DomainEvent):
    @staticmethod
    def create(
        org_id: OrgId,
        position_id: PositionId,
        fields: Dict[str, Any],
        triggered_by: Optional[UserId],
    ):
        return PositionUpdated(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="PositionUpdated",
            payload={"position_id": position_id, "fields": fields},
        )


@dataclass
class PositionDeleted(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, position_id: PositionId, triggered_by: Optional[UserId]):
        return PositionDeleted(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="PositionDeleted",
            payload={"position_id": position_id},
        )


# Position assignment events
@dataclass
class PositionAssigned(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, position_id: PositionId, user_id: UserId, triggered_by: Optional[UserId]):
        return PositionAssigned(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="PositionAssigned",
            payload={"position_id": position_id, "user_id": user_id},
        )


@dataclass
class PositionUnassigned(DomainEvent):
    @staticmethod
    def create(org_id: OrgId, position_id: PositionId, user_id: UserId, triggered_by: Optional[UserId]):
        return PositionUnassigned(
            org_id=org_id,
            occurred_at=_ts(),
            triggered_by=triggered_by,
            name="PositionUnassigned",
            payload={"position_id": position_id, "user_id": user_id},
        )

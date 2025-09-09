from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .value_objects import EventTypeId, OrgId, UserId


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

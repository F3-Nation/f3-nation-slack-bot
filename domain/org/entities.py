from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .events import EventTypeCreated, EventTypeDeleted, EventTypeUpdated
from .value_objects import (
    Acronym,
    EventTagId,
    EventTagName,
    EventTypeId,
    EventTypeName,
    OrgId,
    PositionId,
    PositionName,
    UserId,
)


# Simple in-memory id generation placeholders (will be replaced by persistence layer mapping)
class _IdSeq:
    def __init__(self):
        self._v = 0

    def next(self):
        self._v += 1
        return self._v


_event_type_seq = _IdSeq()
_event_tag_seq = _IdSeq()
_position_seq = _IdSeq()


@dataclass
class EventType:
    id: EventTypeId
    name: EventTypeName
    acronym: Acronym
    category: str  # keeping simple for now
    is_active: bool = True


@dataclass
class EventTag:
    id: EventTagId
    name: EventTagName
    color: str
    is_active: bool = True


@dataclass
class Position:
    id: PositionId
    name: PositionName
    description: Optional[str] = None
    is_active: bool = True


@dataclass
class Org:
    id: OrgId
    parent_id: Optional[OrgId]
    type: str  # region, ao, etc.
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    logo_url: Optional[str] = None
    version: int = 0
    # collections
    event_types: Dict[EventTypeId, EventType] = field(default_factory=dict)
    event_tags: Dict[EventTagId, EventTag] = field(default_factory=dict)
    positions: Dict[PositionId, Position] = field(default_factory=dict)
    admin_user_ids: List[UserId] = field(default_factory=list)
    _events: List[object] = field(default_factory=list, init=False)

    # indexes for invariants
    _event_type_names: set[str] = field(default_factory=set, init=False)
    _event_type_acronyms: set[str] = field(default_factory=set, init=False)
    _event_tag_names: set[str] = field(default_factory=set, init=False)
    _position_names: set[str] = field(default_factory=set, init=False)

    # --- domain behavior ---
    def record(self, event):
        self._events.append(event)

    @property
    def events(self):
        return list(self._events)

    # Event Types
    def add_event_type(self, name: str, category: str, acronym: Optional[str], triggered_by: Optional[UserId]):
        norm_name = name.strip().lower()
        if norm_name in self._event_type_names:
            raise ValueError("Duplicate event type name")
        acro = (acronym or name[:2]).upper()
        if acro in self._event_type_acronyms:
            raise ValueError("Duplicate event type acronym")
        et_id = EventTypeId(_event_type_seq.next())
        et = EventType(id=et_id, name=EventTypeName(name), acronym=Acronym(acro), category=category)
        self.event_types[et_id] = et
        self._event_type_names.add(norm_name)
        self._event_type_acronyms.add(acro)
        self.record(EventTypeCreated.create(self.id, et_id, et.name.value, et.acronym.value, triggered_by))
        return et

    def update_event_type(
        self,
        event_type_id: EventTypeId,
        *,
        name: Optional[str] = None,
        acronym: Optional[str] = None,
        category: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
    ):
        et = self.event_types.get(event_type_id)
        if not et or not et.is_active:
            raise ValueError("Event type not found")
        changes = {}
        if name:
            norm_name = name.strip().lower()
            if norm_name != et.name.value.lower() and norm_name in self._event_type_names:
                raise ValueError("Duplicate event type name")
            self._event_type_names.discard(et.name.value.lower())
            et.name = EventTypeName(name)
            self._event_type_names.add(norm_name)
            changes["name"] = et.name.value
        if acronym:
            acro = acronym.upper()
            if acro != et.acronym.value and acro in self._event_type_acronyms:
                raise ValueError("Duplicate event type acronym")
            self._event_type_acronyms.discard(et.acronym.value)
            et.acronym = Acronym(acro)
            self._event_type_acronyms.add(acro)
            changes["acronym"] = et.acronym.value
        if category:
            et.category = category
            changes["category"] = category
        if changes:
            self.record(EventTypeUpdated.create(self.id, event_type_id, changes, triggered_by))
        return et

    def soft_delete_event_type(self, event_type_id: EventTypeId, triggered_by: Optional[UserId]):
        et = self.event_types.get(event_type_id)
        if not et or not et.is_active:
            raise ValueError("Event type not found")
        # additional rule: we could check references count via domain service before allowing
        et.is_active = False
        self.record(EventTypeDeleted.create(self.id, event_type_id, triggered_by))

    # Admin management
    def assign_admin(self, user_id: UserId):
        if user_id not in self.admin_user_ids:
            self.admin_user_ids.append(user_id)

    def revoke_admin(self, user_id: UserId):
        if user_id in self.admin_user_ids:
            if len(self.admin_user_ids) == 1:
                raise ValueError("Cannot remove last admin")
            self.admin_user_ids.remove(user_id)

    def replace_admins(self, new_admin_user_ids: List[UserId]):
        if not new_admin_user_ids:
            raise ValueError("At least one admin required")
        self.admin_user_ids = list(dict.fromkeys(new_admin_user_ids))  # preserve order, remove dups

    # bootstrap indexes (for reconstitution from persistence)
    def rebuild_indexes(self):
        self._event_type_names = {et.name.value.lower() for et in self.event_types.values() if et.is_active}
        self._event_type_acronyms = {et.acronym.value for et in self.event_types.values() if et.is_active}
        self._event_tag_names = {t.name.value.lower() for t in self.event_tags.values() if t.is_active}
        self._position_names = {p.name.value.lower() for p in self.positions.values() if p.is_active}
        return self

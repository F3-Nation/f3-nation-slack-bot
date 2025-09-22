from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import (
    EventTagCreated,
    EventTagDeleted,
    EventTagUpdated,
    EventTypeCreated,
    EventTypeDeleted,
    EventTypeUpdated,
    LocationCreated,
    LocationDeleted,
    LocationUpdated,
    PositionAssigned,
    PositionCreated,
    PositionDeleted,
    PositionUnassigned,
    PositionUpdated,
)
from .value_objects import (
    Acronym,
    EventTagId,
    EventTagName,
    EventTypeId,
    EventTypeName,
    LocationId,
    LocationName,
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
_location_seq = _IdSeq()


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
    org_type: Optional[str] = None  # 'region', 'ao', etc. None applies to all levels
    description: Optional[str] = None
    is_active: bool = True


@dataclass
class Location:
    id: LocationId
    name: LocationName
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_street: Optional[str] = None
    address_street2: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    is_active: bool = True
    # If True, this location was loaded from persistence with a blank name; the
    # in-memory name is a display fallback only and should not be persisted
    # back unless explicitly renamed via update_location(name=...).
    legacy_blank_name: bool = False


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
    # AO/Org-specific metadata and preferences
    meta: Optional[Dict[str, Any]] = None
    default_location_id: Optional[int] = None
    version: int = 0
    # collections
    event_types: Dict[EventTypeId, EventType] = field(default_factory=dict)
    event_tags: Dict[EventTagId, EventTag] = field(default_factory=dict)
    positions: Dict[PositionId, Position] = field(default_factory=dict)
    locations: Dict[LocationId, Location] = field(default_factory=dict)
    admin_user_ids: List[UserId] = field(default_factory=list)
    # position assignments: position_id -> set[user_id]
    position_assignments: Dict[PositionId, set[UserId]] = field(default_factory=dict)
    _events: List[object] = field(default_factory=list, init=False)

    # indexes for invariants
    _event_type_names: set[str] = field(default_factory=set, init=False)
    _event_type_acronyms: set[str] = field(default_factory=set, init=False)
    _event_tag_names: set[str] = field(default_factory=set, init=False)
    _position_names: set[str] = field(default_factory=set, init=False)
    # position name uniqueness by org_type; None means applies to all levels (conflicts with any)
    _position_names_by_type: Dict[Optional[str], set[str]] = field(default_factory=dict, init=False)
    _location_names: set[str] = field(default_factory=set, init=False)
    # global catalogs (names/acronyms) to extend invariants across global types/tags
    _global_event_type_names: set[str] = field(default_factory=set, init=False)
    _global_event_type_acronyms: set[str] = field(default_factory=set, init=False)
    _global_event_tag_names: set[str] = field(default_factory=set, init=False)
    # global catalog for positions by org_type
    _global_position_names_by_type: Dict[Optional[str], set[str]] = field(default_factory=dict, init=False)

    # --- domain behavior ---
    def record(self, event):
        self._events.append(event)

    @property
    def events(self):
        return list(self._events)

    # Event Types
    def add_event_type(
        self,
        name: str,
        category: str,
        acronym: Optional[str],
        triggered_by: Optional[UserId],
        *,
        allow_global_duplicate: bool = False,
    ):
        norm_name = name.strip().lower()
        if norm_name in self._event_type_names:
            raise ValueError("Duplicate event type name")
        acro = (acronym or name[:2]).upper()
        if acro in self._event_type_acronyms:
            raise ValueError("Duplicate event type acronym")
        # Global catalog invariants (names + acronyms)
        if not allow_global_duplicate:
            if norm_name in self._global_event_type_names:
                raise ValueError("Duplicate event type name (conflicts with global)")
            if acro in self._global_event_type_acronyms:
                raise ValueError("Duplicate event type acronym (conflicts with global)")
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
        allow_global_duplicate: bool = False,
    ):
        et = self.event_types.get(event_type_id)
        if not et or not et.is_active:
            raise ValueError("Event type not found")
        changes = {}
        if name:
            norm_name = name.strip().lower()
            if norm_name != et.name.value.lower() and norm_name in self._event_type_names:
                raise ValueError("Duplicate event type name")
            if (
                not allow_global_duplicate
                and norm_name != et.name.value.lower()
                and norm_name in self._global_event_type_names
            ):
                raise ValueError("Duplicate event type name (conflicts with global)")
            self._event_type_names.discard(et.name.value.lower())
            et.name = EventTypeName(name)
            self._event_type_names.add(norm_name)
            changes["name"] = et.name.value
        if acronym:
            acro = acronym.upper()
            if acro != et.acronym.value and acro in self._event_type_acronyms:
                raise ValueError("Duplicate event type acronym")
            if not allow_global_duplicate and acro != et.acronym.value and acro in self._global_event_type_acronyms:
                raise ValueError("Duplicate event type acronym (conflicts with global)")
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

    # Event Tags
    def add_event_tag(
        self,
        name: str,
        color: str,
        triggered_by: Optional[UserId],
        *,
        allow_global_duplicate: bool = False,
    ):
        norm_name = name.strip().lower()
        if norm_name in self._event_tag_names:
            raise ValueError("Duplicate event tag name")
        if not allow_global_duplicate and norm_name in self._global_event_tag_names:
            raise ValueError("Duplicate event tag name (conflicts with global)")
        tag_id = EventTagId(_event_tag_seq.next())
        tag = EventTag(id=tag_id, name=EventTagName(name), color=color)
        self.event_tags[tag_id] = tag
        self._event_tag_names.add(norm_name)
        self.record(EventTagCreated.create(self.id, tag_id, tag.name.value, tag.color, triggered_by))
        return tag

    def update_event_tag(
        self,
        event_tag_id: EventTagId,
        *,
        name: Optional[str] = None,
        color: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
        allow_global_duplicate: bool = False,
    ):
        tag = self.event_tags.get(event_tag_id)
        if not tag or not tag.is_active:
            raise ValueError("Event tag not found")
        changes = {}
        if name:
            norm_name = name.strip().lower()
            if norm_name != tag.name.value.lower() and norm_name in self._event_tag_names:
                raise ValueError("Duplicate event tag name")
            if (
                not allow_global_duplicate
                and norm_name != tag.name.value.lower()
                and norm_name in self._global_event_tag_names
            ):
                raise ValueError("Duplicate event tag name (conflicts with global)")
            self._event_tag_names.discard(tag.name.value.lower())
            tag.name = EventTagName(name)
            self._event_tag_names.add(norm_name)
            changes["name"] = tag.name.value
        if color:
            tag.color = color
            changes["color"] = color
        if changes:
            self.record(EventTagUpdated.create(self.id, event_tag_id, changes, triggered_by))
        return tag

    def soft_delete_event_tag(self, event_tag_id: EventTagId, triggered_by: Optional[UserId]):
        tag = self.event_tags.get(event_tag_id)
        if not tag or not tag.is_active:
            raise ValueError("Event tag not found")
        tag.is_active = False
        self.record(EventTagDeleted.create(self.id, event_tag_id, triggered_by))

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
        # Legacy flat set for backward compat (may be removed later)
        self._position_names = {p.name.value.lower() for p in self.positions.values() if p.is_active}
        # Build per-type name indexes (exclude inactive)
        names_by_type: Dict[Optional[str], set[str]] = {}
        for p in self.positions.values():
            if not p.is_active:
                continue
            key = p.org_type or None
            bucket = names_by_type.setdefault(key, set())
            bucket.add(p.name.value.lower())
        self._position_names_by_type = names_by_type
        # Exclude legacy blank-name locations from uniqueness index to avoid false collisions
        self._location_names = {
            loc.name.value.lower()
            for loc in self.locations.values()
            if loc.is_active and not getattr(loc, "legacy_blank_name", False)
        }
        return self

    # --- Position assignments ---
    def assign_user_to_position(
        self, position_id: PositionId, user_id: UserId, triggered_by: Optional[UserId] = None
    ) -> None:
        p = self.positions.get(position_id)
        if not p or not p.is_active:
            raise ValueError("Position not found")
        bucket = self.position_assignments.setdefault(position_id, set())
        if user_id in bucket:
            return  # idempotent
        bucket.add(user_id)
        self.record(PositionAssigned.create(self.id, position_id, user_id, triggered_by))

    def unassign_user_from_position(
        self, position_id: PositionId, user_id: UserId, triggered_by: Optional[UserId] = None
    ) -> None:
        bucket = self.position_assignments.get(position_id)
        if not bucket or user_id not in bucket:
            return  # idempotent
        bucket.discard(user_id)
        self.record(PositionUnassigned.create(self.id, position_id, user_id, triggered_by))

    def replace_position_assignments(
        self, position_id: PositionId, user_ids: List[UserId], triggered_by: Optional[UserId] = None
    ) -> None:
        p = self.positions.get(position_id)
        if not p or not p.is_active:
            raise ValueError("Position not found")
        # Current assignments
        current = self.position_assignments.get(position_id, set())
        new_set = set(user_ids)
        # Unassign removed
        for uid in list(current - new_set):
            self.unassign_user_from_position(position_id, uid, triggered_by)
        # Assign new
        for uid in list(new_set - current):
            self.assign_user_to_position(position_id, uid, triggered_by)

    # Allow infrastructure/application layer to set global catalogs for invariants
    def set_global_catalog(
        self,
        *,
        event_type_names: Optional[set[str]] = None,
        event_type_acronyms: Optional[set[str]] = None,
        event_tag_names: Optional[set[str]] = None,
        position_names_by_type: Optional[Dict[Optional[str], set[str]]] = None,
    ) -> "Org":
        self._global_event_type_names = {x.strip().lower() for x in (event_type_names or set())}
        self._global_event_type_acronyms = {x.strip().upper() for x in (event_type_acronyms or set())}
        self._global_event_tag_names = {x.strip().lower() for x in (event_tag_names or set())}
        # Normalize position names per type (keys can be strings like 'region', 'ao', or None)
        pos_map: Dict[Optional[str], set[str]] = {}
        if position_names_by_type:
            for k, v in position_names_by_type.items():
                normk = k if k is None else str(k).strip().lower() or None
                pos_map[normk] = {x.strip().lower() for x in (v or set())}
        self._global_position_names_by_type = pos_map
        return self

    # Locations
    def add_location(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        address_street: Optional[str] = None,
        address_street2: Optional[str] = None,
        address_city: Optional[str] = None,
        address_state: Optional[str] = None,
        address_zip: Optional[str] = None,
        address_country: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
    ) -> Location:
        norm = (name or "").strip().lower()
        if not norm:
            raise ValueError("Location name cannot be empty")
        if norm in self._location_names:
            raise ValueError("Duplicate location name")
        loc_id = LocationId(_location_seq.next())
        loc = Location(
            id=loc_id,
            name=LocationName(name),
            description=description,
            latitude=latitude,
            longitude=longitude,
            address_street=address_street,
            address_street2=address_street2,
            address_city=address_city,
            address_state=address_state,
            address_zip=address_zip,
            address_country=address_country,
        )
        self.locations[loc_id] = loc
        self._location_names.add(norm)
        self.record(LocationCreated.create(self.id, loc_id, loc.name.value, triggered_by))
        return loc

    def update_location(
        self,
        location_id: LocationId,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        address_street: Optional[str] = None,
        address_street2: Optional[str] = None,
        address_city: Optional[str] = None,
        address_state: Optional[str] = None,
        address_zip: Optional[str] = None,
        address_country: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
    ) -> Location:
        loc = self.locations.get(location_id)
        if not loc or not loc.is_active:
            raise ValueError("Location not found")
        changes: dict = {}
        if name is not None:
            norm = (name or "").strip().lower()
            if not norm:
                raise ValueError("Location name cannot be empty")
            if norm != loc.name.value.lower() and norm in self._location_names:
                raise ValueError("Duplicate location name")
            self._location_names.discard(loc.name.value.lower())
            loc.name = LocationName(name)
            # Explicit rename clears legacy blank-name status so name will persist
            if getattr(loc, "legacy_blank_name", False):
                loc.legacy_blank_name = False
            self._location_names.add(norm)
            changes["name"] = loc.name.value
        if description is not None:
            loc.description = description
            changes["description"] = description
        if latitude is not None:
            loc.latitude = latitude
            changes["latitude"] = latitude
        if longitude is not None:
            loc.longitude = longitude
            changes["longitude"] = longitude
        if address_street is not None:
            loc.address_street = address_street
            changes["address_street"] = address_street
        if address_street2 is not None:
            loc.address_street2 = address_street2
            changes["address_street2"] = address_street2
        if address_city is not None:
            loc.address_city = address_city
            changes["address_city"] = address_city
        if address_state is not None:
            loc.address_state = address_state
            changes["address_state"] = address_state
        if address_zip is not None:
            loc.address_zip = address_zip
            changes["address_zip"] = address_zip
        if address_country is not None:
            loc.address_country = address_country
            changes["address_country"] = address_country
        if changes:
            self.record(LocationUpdated.create(self.id, location_id, changes, triggered_by))
        return loc

    def soft_delete_location(self, location_id: LocationId, triggered_by: Optional[UserId]):
        loc = self.locations.get(location_id)
        if not loc or not loc.is_active:
            raise ValueError("Location not found")
        loc.is_active = False
        self.record(LocationDeleted.create(self.id, location_id, triggered_by))

    # Positions
    def _conflicts_with_position_name(
        self,
        name_norm: str,
        org_type: Optional[str],
        *,
        exclude_name_norm: Optional[str] = None,
    ) -> bool:
        """Check if a name conflicts for a given org_type, considering wildcard None bucket.
        exclude_name_norm: if provided, ignore this existing normalized name when checking (for updates).
        """
        key = org_type.strip().lower() if isinstance(org_type, str) else None
        # local buckets
        local_exact = self._position_names_by_type.get(key, set())
        local_all = self._position_names_by_type.get(None, set())
        # global buckets
        global_exact = self._global_position_names_by_type.get(key, set())
        global_all = self._global_position_names_by_type.get(None, set())

        def present_in(bucket: set[str]) -> bool:
            if exclude_name_norm is not None and name_norm == exclude_name_norm:
                return False
            return name_norm in bucket

        # Conflict if present in same type or wildcard type
        return any(
            present_in(b)
            for b in (
                local_exact,
                local_all,
                global_exact,
                global_all,
            )
        )

    def add_position(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        org_type: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
        allow_global_duplicate: bool = False,
    ) -> Position:
        norm = (name or "").strip().lower()
        if not norm:
            raise ValueError("Position name cannot be empty")
        # Local conflict check
        if self._conflicts_with_position_name(norm, org_type):
            raise ValueError("Duplicate position name for this org level")
        # Global catalog check (unless allowed)
        if not allow_global_duplicate:
            key = org_type.strip().lower() if isinstance(org_type, str) else None
            if norm in self._global_position_names_by_type.get(
                key, set()
            ) or norm in self._global_position_names_by_type.get(None, set()):
                raise ValueError("Duplicate position name (conflicts with global for this org level)")
        pos_id = PositionId(_position_seq.next())
        p = Position(
            id=pos_id,
            name=PositionName(name),
            org_type=(org_type.strip().lower() if isinstance(org_type, str) else None),
            description=description,
        )
        self.positions[pos_id] = p
        # Update indexes
        bucket = self._position_names_by_type.setdefault(p.org_type, set())
        bucket.add(norm)
        # legacy flat set
        self._position_names.add(norm)
        self.record(PositionCreated.create(self.id, pos_id, p.name.value, p.org_type, triggered_by))
        return p

    def update_position(
        self,
        position_id: PositionId,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        org_type: Optional[str] = None,
        triggered_by: Optional[UserId] = None,
        allow_global_duplicate: bool = False,
    ) -> Position:
        p = self.positions.get(position_id)
        if not p or not p.is_active:
            raise ValueError("Position not found")
        changes: Dict[str, object] = {}
        new_name_norm = p.name.value.lower()
        new_type_norm: Optional[str] = p.org_type
        # Compute prospective values
        if name is not None:
            n = (name or "").strip()
            if not n:
                raise ValueError("Position name cannot be empty")
            new_name_norm = n.lower()
        if org_type is not None:
            t = org_type.strip().lower() if isinstance(org_type, str) else None
            new_type_norm = t
        # Conflict if changed name or type collides locally or globally
        if (new_name_norm != p.name.value.lower()) or (new_type_norm != p.org_type):
            # Remove existing from index temporarily
            # Check local conflicts excluding current name in its bucket
            # We'll simulate exclusion by passing exclude_name_norm if bucket is same type;
            # but also need to remove from old bucket when type changes
            # For simplicity, check conflicts in target buckets ignoring our own current entry
            if self._conflicts_with_position_name(
                new_name_norm,
                new_type_norm,
                exclude_name_norm=p.name.value.lower() if new_type_norm == p.org_type else None,
            ):
                raise ValueError("Duplicate position name for this org level")
            if not allow_global_duplicate:
                if new_name_norm in self._global_position_names_by_type.get(
                    new_type_norm, set()
                ) or new_name_norm in self._global_position_names_by_type.get(None, set()):
                    raise ValueError("Duplicate position name (conflicts with global for this org level)")
        # Apply changes and update indexes
        # Remove old index entry
        old_bucket = self._position_names_by_type.setdefault(p.org_type, set())
        old_bucket.discard(p.name.value.lower())
        if name is not None:
            p.name = PositionName(name)
            changes["name"] = p.name.value
        if description is not None:
            p.description = description
            changes["description"] = description
        if org_type is not None:
            p.org_type = org_type.strip().lower() if isinstance(org_type, str) else None
            changes["org_type"] = p.org_type
        # Add new index entry
        new_bucket = self._position_names_by_type.setdefault(p.org_type, set())
        new_bucket.add(p.name.value.lower())
        self._position_names.add(p.name.value.lower())
        if changes:
            self.record(PositionUpdated.create(self.id, position_id, changes, triggered_by))
        return p

    def soft_delete_position(self, position_id: PositionId, triggered_by: Optional[UserId]):
        p = self.positions.get(position_id)
        if not p or not p.is_active:
            raise ValueError("Position not found")
        p.is_active = False
        # Remove from indexes
        bucket = self._position_names_by_type.setdefault(p.org_type, set())
        bucket.discard(p.name.value.lower())
        self._position_names.discard(p.name.value.lower())
        self.record(PositionDeleted.create(self.id, position_id, triggered_by))

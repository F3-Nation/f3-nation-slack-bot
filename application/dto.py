from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class LocationDTO:
    id: int
    name: str
    description: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    address_street: Optional[str]
    address_street2: Optional[str]
    address_city: Optional[str]
    address_state: Optional[str]
    address_zip: Optional[str]
    address_country: Optional[str]


@dataclass(frozen=True)
class EventTypeDTO:
    id: int
    name: str
    acronym: Optional[str]
    category: Optional[str]
    scope: Literal["global", "region"]


@dataclass(frozen=True)
class EventTagDTO:
    id: int
    name: str
    color: str
    scope: Literal["global", "region"]


@dataclass(frozen=True)
class PositionDTO:
    id: int
    name: str
    description: Optional[str]
    org_type: Optional[str]
    scope: Literal["global", "region"]


# --- Mapping helpers (domain -> DTO) ---
def to_location_dto(loc) -> LocationDTO:  # domain.org.entities.Location
    # Location.name may be a value object
    name_val = getattr(loc.name, "value", loc.name)
    return LocationDTO(
        id=int(loc.id),
        name=str(name_val),
        description=getattr(loc, "description", None),
        latitude=getattr(loc, "latitude", None),
        longitude=getattr(loc, "longitude", None),
        address_street=getattr(loc, "address_street", None),
        address_street2=getattr(loc, "address_street2", None),
        address_city=getattr(loc, "address_city", None),
        address_state=getattr(loc, "address_state", None),
        address_zip=getattr(loc, "address_zip", None),
        address_country=getattr(loc, "address_country", None),
    )


def to_event_type_dto(et, *, scope: Literal["global", "region"]) -> EventTypeDTO:
    name_val = getattr(et.name, "value", et.name)
    acronym_val = getattr(et, "acronym", None)
    if hasattr(acronym_val, "value"):
        acronym_val = acronym_val.value
    return EventTypeDTO(
        id=int(et.id),
        name=str(name_val),
        acronym=acronym_val,
        category=getattr(et, "category", None),
        scope=scope,
    )


def to_event_tag_dto(tag, *, scope: Literal["global", "region"]) -> EventTagDTO:
    name_val = getattr(tag.name, "value", tag.name)
    return EventTagDTO(
        id=int(tag.id),
        name=str(name_val),
        color=getattr(tag, "color", "#000000"),
        scope=scope,
    )


def to_position_dto(pos, *, scope: Literal["global", "region"]) -> PositionDTO:
    name_val = getattr(pos.name, "value", pos.name)
    org_type_val = getattr(pos, "org_type", None)
    return PositionDTO(
        id=int(pos.id),
        name=str(name_val),
        description=getattr(pos, "description", None),
        org_type=(str(org_type_val) if org_type_val is not None else None),
        scope=scope,
    )

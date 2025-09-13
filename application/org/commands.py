from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UpdateRegionProfile:
    org_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    logo_url: Optional[str] = None
    admin_user_ids: Optional[list[int]] = None
    SENTINEL = object()


# --- Event Tag Commands ---


@dataclass
class AddEventTag:
    org_id: int
    name: str
    color: str
    triggered_by: Optional[int] = None


@dataclass
class UpdateEventTag:
    org_id: int
    tag_id: int
    name: Optional[str] = None
    color: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class SoftDeleteEventTag:
    org_id: int
    tag_id: int
    triggered_by: Optional[int] = None


@dataclass
class CloneGlobalEventTag:
    org_id: int
    global_tag_id: int
    triggered_by: Optional[int] = None


# --- Event Type Commands ---


@dataclass
class AddEventType:
    org_id: int
    name: str
    category: str
    acronym: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class UpdateEventType:
    org_id: int
    event_type_id: int
    name: Optional[str] = None
    category: Optional[str] = None
    acronym: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class SoftDeleteEventType:
    org_id: int
    event_type_id: int
    triggered_by: Optional[int] = None


@dataclass
class CloneGlobalEventType:
    org_id: int
    global_event_type_id: int
    triggered_by: Optional[int] = None


# --- Location Commands ---


@dataclass
class AddLocation:
    org_id: int
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_street: Optional[str] = None
    address_street2: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class UpdateLocation:
    org_id: int
    location_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_street: Optional[str] = None
    address_street2: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    address_country: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class SoftDeleteLocation:
    org_id: int
    location_id: int
    triggered_by: Optional[int] = None


# --- AO (child Org) Commands ---


@dataclass
class CreateAo:
    region_id: int
    name: str
    description: Optional[str] = None
    default_location_id: Optional[int] = None
    slack_channel_id: Optional[str] = None
    logo_url: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class UpdateAoProfile:
    ao_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    default_location_id: Optional[int] = None
    slack_channel_id: Optional[str] = None
    logo_url: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class DeactivateAo:
    ao_id: int
    triggered_by: Optional[int] = None

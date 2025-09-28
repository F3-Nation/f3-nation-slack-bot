from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Set, Tuple

from f3_data_models.models import EventTag as SAEventTag  # type: ignore
from f3_data_models.models import EventType as SAEventType  # type: ignore
from f3_data_models.models import Location as SALocation  # type: ignore
from f3_data_models.models import Org as SAOrg  # type: ignore
from f3_data_models.models import Org_Type as SAOrgType  # type: ignore
from f3_data_models.models import Position as SAPosition  # type: ignore
from f3_data_models.models import Position_x_Org_x_User as SAPositionAssignment  # type: ignore
from f3_data_models.models import Role as SARole  # type: ignore
from f3_data_models.models import Role_x_User_x_Org as SARoleAssignment  # type: ignore
from f3_data_models.utils import DbManager

from domain.org import entities as domain_entities
from domain.org.entities import EventTag, EventType, Location, Org, Position
from domain.org.events import (
    EventTagCreated,
    EventTagDeleted,
    EventTagUpdated,
    EventTypeCreated,
    EventTypeDeleted,
    EventTypeUpdated,
    LocationCreated,
    LocationDeleted,
    LocationUpdated,
    OrgAdminAssigned,
    OrgAdminRevoked,
    OrgAdminsReplaced,
    OrgProfileUpdated,
    PositionAssigned,
    PositionCreated,
    PositionDeleted,
    PositionUnassigned,
    PositionUpdated,
)
from domain.org.repository import OrgRepository
from domain.org.value_objects import (
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

"""SQLAlchemy implementation of OrgRepository.

This is a placeholder that adapts the existing DbManager / f3_data_models models.
Later we can optimize queries and handle version checking.
"""


class SqlAlchemyOrgRepository(OrgRepository):
    # Simple in-process TTL cache for global catalogs to avoid frequent DB hits
    _GLOBAL_CACHE: dict = {
        "expires": 0.0,
        "type_names": set(),
        "type_acros": set(),
        "tag_names": set(),
        "position_names_by_type": {},
    }
    _GLOBAL_TTL_SEC: int = int(os.environ.get("ORG_GLOBAL_CATALOG_TTL", "300"))

    @staticmethod
    def _to_sa_org_type(key: Optional[str]):
        """Map normalized org_type key (e.g., 'region', 'ao') to SA enum if available."""
        if not key:
            return None
        try:
            return SAOrgType[key]
        except Exception:
            return None

    @classmethod
    def _get_global_catalog(
        cls,
    ) -> Tuple[Set[str], Set[str], Set[str], Dict[Optional[str], Set[str]], Dict[int, Position]]:
        now = time.time()
        # Fast path: return cached 5‑tuple (includes global position domain objects)
        if now < float(cls._GLOBAL_CACHE.get("expires", 0)):
            return (
                set(cls._GLOBAL_CACHE.get("type_names", set())),
                set(cls._GLOBAL_CACHE.get("type_acros", set())),
                set(cls._GLOBAL_CACHE.get("tag_names", set())),
                dict(cls._GLOBAL_CACHE.get("position_names_by_type", {})),
                dict(cls._GLOBAL_CACHE.get("global_positions", {})),
            )

        # Fetch active global (specific_org_id is NULL) types/tags
        type_filters = [SAEventType.specific_org_id.is_(None)]
        if hasattr(SAEventType, "is_active"):
            type_filters.append(SAEventType.is_active.is_(True))
        tag_filters = [SAEventTag.specific_org_id.is_(None)]
        if hasattr(SAEventTag, "is_active"):
            tag_filters.append(SAEventTag.is_active.is_(True))
        global_types = DbManager.find_records(SAEventType, type_filters)
        global_tags = DbManager.find_records(SAEventTag, tag_filters)

        # Global positions are those with org_id is NULL
        pos_filters = [SAPosition.org_id.is_(None)]
        global_position_rows = DbManager.find_records(SAPosition, pos_filters)

        type_names = {str(getattr(t, "name", "")).strip().lower() for t in global_types if getattr(t, "name", None)}
        type_acros = {
            (str(getattr(t, "acronym", None)) or str(getattr(t, "name", ""))[:2]).strip().upper() for t in global_types
        }
        tag_names = {str(getattr(t, "name", "")).strip().lower() for t in global_tags if getattr(t, "name", None)}

        # Build map of org_type -> set of names (normalized lower)
        pos_map: Dict[Optional[str], Set[str]] = {}
        global_position_map: Dict[int, Position] = {}
        for p in global_position_rows:
            key: Optional[str] = None
            ot = getattr(p, "org_type", None)
            if ot is not None:
                try:
                    key = str(ot.name).strip().lower()
                except Exception:
                    key = str(ot).strip().lower()
            bucket = pos_map.setdefault(key, set())
            raw_name = str(getattr(p, "name", "")).strip()
            nm = raw_name.lower()
            if nm:
                bucket.add(nm)
            # Build domain Position (treat all global as active)
            global_position_map[p.id] = Position(
                id=PositionId(p.id),
                name=PositionName(raw_name),
                org_type=key,
                description=getattr(p, "description", None),
                is_active=True,
            )

        cls._GLOBAL_CACHE = {
            "expires": now + cls._GLOBAL_TTL_SEC,
            "type_names": type_names,
            "type_acros": type_acros,
            "tag_names": tag_names,
            "position_names_by_type": pos_map,
            "global_positions": global_position_map,
        }
        return set(type_names), set(type_acros), set(tag_names), pos_map, global_position_map

    def get(self, org_id: OrgId) -> Optional[Org]:
        sa_org: SAOrg = DbManager.get(SAOrg, org_id)
        if not sa_org:
            return None
        # build aggregate (minimal fields for now)
        org = Org(
            id=OrgId(sa_org.id),
            parent_id=OrgId(sa_org.parent_id) if sa_org.parent_id else None,
            type=sa_org.org_type.name if getattr(sa_org, "org_type", None) else "region",
            name=sa_org.name,
            description=sa_org.description,
            website=getattr(sa_org, "website", None),
            email=getattr(sa_org, "email", None),
            twitter=getattr(sa_org, "twitter", None),
            facebook=getattr(sa_org, "facebook", None),
            instagram=getattr(sa_org, "instagram", None),
            logo_url=getattr(sa_org, "logo_url", None),
            meta=getattr(sa_org, "meta", None),
            default_location_id=getattr(sa_org, "default_location_id", None),
            version=getattr(sa_org, "version", 0) or 0,
        )
        # load custom event types for this org
        event_type_records = DbManager.find_records(
            SAEventType,
            [SAEventType.specific_org_id == sa_org.id],  # include inactive for soft delete visibility
        )
        max_type_id = 0
        for rec in event_type_records:
            et = EventType(
                id=EventTypeId(rec.id),
                name=EventTypeName(rec.name),
                acronym=Acronym(rec.acronym or rec.name[:2]),
                category=getattr(rec, "event_category", "first_f"),
                is_active=rec.is_active,
            )
            org.event_types[et.id] = et
            if rec.id and rec.id > max_type_id:
                max_type_id = rec.id
        # load custom event tags for this org
        # include both active and inactive to preserve soft-deleted items in aggregate
        event_tag_records = DbManager.find_records(
            SAEventTag,
            [SAEventTag.specific_org_id == sa_org.id],
        )
        max_tag_id = 0
        for rec in event_tag_records:
            tag = EventTag(
                id=EventTagId(rec.id),
                name=EventTagName(rec.name),
                color=rec.color,
                is_active=rec.is_active,
            )
            org.event_tags[tag.id] = tag
            if rec.id and rec.id > max_tag_id:
                max_tag_id = rec.id
        # load locations for this org (active + inactive)
        location_records = DbManager.find_records(SALocation, [SALocation.org_id == sa_org.id])
        max_loc_id = 0
        for rec in location_records:
            raw_name = rec.name or ""
            # Allow hydration of legacy blank-name locations: synthesize a display name
            # and mark legacy_blank_name=True so uniqueness indexing excludes them and
            # the save adapter can write back blank unless renamed.
            display_name = (
                raw_name.strip()
                or (rec.description or rec.address_street or rec.address_city or rec.address_state or rec.address_zip)
                or "Unnamed Location"
            )
            loc = Location(
                id=LocationId(rec.id),
                name=LocationName(display_name),
                description=rec.description,
                latitude=rec.latitude,
                longitude=rec.longitude,
                address_street=rec.address_street,
                address_street2=rec.address_street2,
                address_city=rec.address_city,
                address_state=rec.address_state,
                address_zip=rec.address_zip,
                address_country=rec.address_country,
                is_active=rec.is_active,
                legacy_blank_name=(raw_name.strip() == ""),
            )
            org.locations[loc.id] = loc
            if rec.id and rec.id > max_loc_id:
                max_loc_id = rec.id
        # load positions for this org (no is_active column; treat all as active)
        org_position_records = DbManager.find_records(SAPosition, [SAPosition.org_id == sa_org.id])
        max_pos_id = 0
        for rec in org_position_records:
            # Map SA Org_Type enum to lower-case string key
            ot = getattr(rec, "org_type", None)
            org_type_key: Optional[str] = None
            if ot is not None:
                try:
                    org_type_key = str(ot.name).strip().lower()
                except Exception:
                    org_type_key = str(ot).strip().lower()
            pos = Position(
                id=PositionId(rec.id),
                name=PositionName(rec.name),
                org_type=org_type_key,
                description=rec.description,
                is_active=True,
            )
            org.positions[pos.id] = pos
            if rec.id and rec.id > max_pos_id:
                max_pos_id = rec.id

        # Load position assignments for this org (both local and global positions)
        try:
            assignment_rows = DbManager.find_records(SAPositionAssignment, [SAPositionAssignment.org_id == sa_org.id])
            for rec in assignment_rows:
                pid = PositionId(rec.position_id)
                uid = UserId(rec.user_id)
                bucket = org.position_assignments.setdefault(pid, set())
                bucket.add(uid)
        except Exception:
            # Best-effort: if assignment load fails, continue with empty assignments
            pass
        org.rebuild_indexes()
        # set global catalogs for invariant checks (cached) and augment with parent-region positions
        try:
            type_names, type_acros, tag_names, pos_map, global_positions = self._get_global_catalog()
            # Copy so we can safely augment without mutating cache
            combined_pos_map = {k: set(v) for k, v in (pos_map or {}).items()}
            combined_global_positions: Dict[int, Position] = dict(global_positions or {})

            # If this org has a parent (e.g., AO under a region), make the parent's
            # custom positions visible for lookups/assignments. This allows AOs to
            # assign members to region-defined positions (org_type='ao') like "Site Q".
            if org.parent_id is not None:
                try:
                    parent_positions = DbManager.find_records(SAPosition, [SAPosition.org_id == int(org.parent_id)])
                    for p in parent_positions:
                        # Map SA Org_Type enum/name to normalized string key
                        ot = getattr(p, "org_type", None)
                        key = None
                        if ot is not None:
                            try:
                                key = str(ot.name).strip().lower()
                            except Exception:
                                key = str(ot).strip().lower()
                        # Add name to inherited/global name buckets
                        bucket = combined_pos_map.setdefault(key, set())
                        raw_name = str(getattr(p, "name", "")).strip()
                        if raw_name:
                            bucket.add(raw_name.lower())
                        # Expose parent's position object as read-only/global for this org
                        if p.id not in combined_global_positions:
                            combined_global_positions[p.id] = Position(
                                id=PositionId(p.id),
                                name=PositionName(raw_name),
                                org_type=key,
                                description=getattr(p, "description", None),
                                is_active=True,
                            )
                except Exception:
                    # best-effort: if augmenting with parent positions fails, continue with globals only
                    pass

            org.set_global_catalog(
                event_type_names=type_names,
                event_type_acronyms=type_acros,
                event_tag_names=tag_names,
                position_names_by_type=combined_pos_map,
                positions=combined_global_positions,
            )
        except Exception:
            # best-effort; continue without global catalogs if lookup fails
            pass
        # advance in-memory id sequences to avoid collisions for new domain-created entities
        try:
            if getattr(domain_entities, "_event_type_seq", None) is not None:
                domain_entities._event_type_seq._v = max(domain_entities._event_type_seq._v, int(max_type_id))
            if getattr(domain_entities, "_event_tag_seq", None) is not None:
                domain_entities._event_tag_seq._v = max(domain_entities._event_tag_seq._v, int(max_tag_id))
            if getattr(domain_entities, "_location_seq", None) is not None:
                domain_entities._location_seq._v = max(domain_entities._location_seq._v, int(max_loc_id))
            if getattr(domain_entities, "_position_seq", None) is not None:
                domain_entities._position_seq._v = max(domain_entities._position_seq._v, int(max_pos_id))
        except Exception:  # pragma: no cover - best-effort safety
            pass
        return org

    def list_children(self, parent_id: OrgId, include_inactive: bool = False) -> List[Org]:
        # fetch child orgs (AOs) with this parent
        filters = [SAOrg.parent_id == int(parent_id)]
        if not include_inactive and hasattr(SAOrg, "is_active"):
            filters.append(SAOrg.is_active.is_(True))
        sa_children = DbManager.find_records(SAOrg, filters)
        results: List[Org] = []
        for sa_org in sa_children:
            child = Org(
                id=OrgId(sa_org.id),
                parent_id=OrgId(sa_org.parent_id) if sa_org.parent_id else None,
                type=sa_org.org_type.name if getattr(sa_org, "org_type", None) else "region",
                name=sa_org.name,
                description=sa_org.description,
                website=getattr(sa_org, "website", None),
                email=getattr(sa_org, "email", None),
                twitter=getattr(sa_org, "twitter", None),
                facebook=getattr(sa_org, "facebook", None),
                instagram=getattr(sa_org, "instagram", None),
                logo_url=getattr(sa_org, "logo_url", None),
                meta=getattr(sa_org, "meta", None),
                default_location_id=getattr(sa_org, "default_location_id", None),
                version=getattr(sa_org, "version", 0) or 0,
            )
            # children are returned without loading collections for performance
            child.rebuild_indexes()
            results.append(child)
        return results

    def save(self, org: Org) -> None:
        # Event-driven persistence for aggregate changes
        for evt in org.events:
            # Event Types
            match evt:
                case OrgProfileUpdated():
                    fields = evt.payload.get("fields", {})  # type: ignore[assignment]
                    mapped = {}
                    # list of allowed scalar fields on SAOrg
                    field_map = {
                        "name": SAOrg.name,
                        "description": SAOrg.description,
                        "website": getattr(SAOrg, "website", None),
                        "email": getattr(SAOrg, "email", None),
                        "twitter": getattr(SAOrg, "twitter", None),
                        "facebook": getattr(SAOrg, "facebook", None),
                        "instagram": getattr(SAOrg, "instagram", None),
                        "logo_url": getattr(SAOrg, "logo_url", None),
                    }
                    for k, v in fields.items():
                        sa_col = field_map.get(k)
                        if sa_col is not None:
                            mapped[sa_col] = v
                    if mapped:
                        DbManager.update_record(SAOrg, org.id, mapped)
                    continue
                # Admins
                case OrgAdminsReplaced():
                    if org.type == "region":
                        admin_role = DbManager.find_records(SARole, [SARole.name == "admin"])
                        if not admin_role:
                            raise ValueError("Admin role not found in database")
                        admin_role_id = admin_role[0].id
                        # replace = delete all then insert provided
                        DbManager.delete_records(
                            SARoleAssignment,
                            [SARoleAssignment.org_id == org.id, SARoleAssignment.role_id == admin_role_id],
                        )
                        for uid in evt.payload.get("user_ids", []) or []:  # type: ignore[union-attr]
                            DbManager.create_record(
                                SARoleAssignment(role_id=admin_role_id, org_id=org.id, user_id=int(uid))
                            )
                    continue
                case OrgAdminAssigned():
                    if org.type == "region":
                        admin_role = DbManager.find_records(SARole, [SARole.name == "admin"])
                        if not admin_role:
                            raise ValueError("Admin role not found in database")
                        admin_role_id = admin_role[0].id
                        uid = int(evt.payload.get("user_id"))  # type: ignore[arg-type]
                        existing = DbManager.find_records(
                            SARoleAssignment,
                            [
                                SARoleAssignment.org_id == org.id,
                                SARoleAssignment.role_id == admin_role_id,
                                SARoleAssignment.user_id == uid,
                            ],
                        )
                        if not existing:
                            DbManager.create_record(SARoleAssignment(role_id=admin_role_id, org_id=org.id, user_id=uid))
                    continue
                case OrgAdminRevoked():
                    if org.type == "region":
                        admin_role = DbManager.find_records(SARole, [SARole.name == "admin"])
                        if not admin_role:
                            raise ValueError("Admin role not found in database")
                        admin_role_id = admin_role[0].id
                        uid = int(evt.payload.get("user_id"))  # type: ignore[arg-type]
                        DbManager.delete_records(
                            SARoleAssignment,
                            [
                                SARoleAssignment.org_id == org.id,
                                SARoleAssignment.role_id == admin_role_id,
                                SARoleAssignment.user_id == uid,
                            ],
                        )
                    continue
                case EventTypeCreated():
                    et = org.event_types.get(evt.payload["event_type_id"])  # type: ignore[index]
                    if et is None:
                        continue
                    sa_obj = DbManager.create_record(
                        SAEventType(
                            name=et.name.value,
                            event_category=et.category,
                            acronym=et.acronym.value,
                            specific_org_id=org.id,
                            is_active=et.is_active,
                        )
                    )
                    if sa_obj.id != et.id:
                        old_id = et.id
                        et.id = EventTypeId(sa_obj.id)
                        org.event_types[et.id] = et
                        org.event_types.pop(old_id, None)
                case EventTypeUpdated():
                    et = org.event_types.get(evt.payload["event_type_id"])  # type: ignore[index]
                    if et is None:
                        continue
                    DbManager.update_record(
                        SAEventType,
                        et.id,
                        {
                            SAEventType.name: et.name.value,
                            SAEventType.acronym: et.acronym.value,
                            SAEventType.event_category: et.category,
                            SAEventType.is_active: et.is_active,
                        },
                    )
                case EventTypeDeleted():
                    et_id = evt.payload["event_type_id"]  # type: ignore[index]
                    DbManager.update_record(SAEventType, et_id, {SAEventType.is_active: False})

                # Event Tags
                case EventTagCreated():
                    tag = org.event_tags.get(evt.payload["event_tag_id"])  # type: ignore[index]
                    if tag is None:
                        continue
                    sa_obj = DbManager.create_record(
                        SAEventTag(
                            name=tag.name.value,
                            color=tag.color,
                            specific_org_id=org.id,
                            is_active=tag.is_active,
                        )
                    )
                    if sa_obj.id != tag.id:
                        old_id = tag.id
                        tag.id = EventTagId(sa_obj.id)
                        org.event_tags[tag.id] = tag
                        org.event_tags.pop(old_id, None)
                case EventTagUpdated():
                    tag = org.event_tags.get(evt.payload["event_tag_id"])  # type: ignore[index]
                    if tag is None:
                        continue
                    DbManager.update_record(
                        SAEventTag,
                        tag.id,
                        {
                            SAEventTag.name: tag.name.value,
                            SAEventTag.color: tag.color,
                            SAEventTag.is_active: tag.is_active,
                        },
                    )
                case EventTagDeleted():
                    tag_id = evt.payload["event_tag_id"]  # type: ignore[index]
                    DbManager.update_record(SAEventTag, tag_id, {SAEventTag.is_active: False})

                # Locations
                case LocationCreated():
                    loc = org.locations.get(evt.payload["location_id"])  # type: ignore[index]
                    if loc is None:
                        continue
                    sa_obj = DbManager.create_record(
                        SALocation(
                            name=loc.name.value,
                            description=loc.description,
                            is_active=loc.is_active,
                            latitude=loc.latitude,
                            longitude=loc.longitude,
                            address_street=loc.address_street,
                            address_street2=loc.address_street2,
                            address_city=loc.address_city,
                            address_state=loc.address_state,
                            address_zip=loc.address_zip,
                            address_country=loc.address_country,
                            org_id=org.id,
                        )
                    )
                    if sa_obj.id != loc.id:
                        old_id = loc.id
                        loc.id = LocationId(sa_obj.id)
                        org.locations[loc.id] = loc
                        org.locations.pop(old_id, None)
                case LocationUpdated():
                    loc = org.locations.get(evt.payload["location_id"])  # type: ignore[index]
                    if loc is None:
                        continue
                    name_to_persist = loc.name.value if not getattr(loc, "legacy_blank_name", False) else ""
                    DbManager.update_record(
                        SALocation,
                        loc.id,
                        {
                            SALocation.name: name_to_persist,
                            SALocation.description: loc.description,
                            SALocation.is_active: loc.is_active,
                            SALocation.latitude: loc.latitude,
                            SALocation.longitude: loc.longitude,
                            SALocation.address_street: loc.address_street,
                            SALocation.address_street2: loc.address_street2,
                            SALocation.address_city: loc.address_city,
                            SALocation.address_state: loc.address_state,
                            SALocation.address_zip: loc.address_zip,
                            SALocation.address_country: loc.address_country,
                        },
                    )
                case LocationDeleted():
                    loc_id = evt.payload["location_id"]  # type: ignore[index]
                    DbManager.update_record(SALocation, loc_id, {SALocation.is_active: False})

                # Positions
                case PositionCreated():
                    pos = org.positions.get(evt.payload["position_id"])  # type: ignore[index]
                    if pos is None:
                        continue
                    sa_org_type = self._to_sa_org_type(pos.org_type)
                    sa_obj = DbManager.create_record(
                        SAPosition(
                            name=pos.name.value,
                            description=pos.description,
                            org_type=sa_org_type,
                            org_id=org.id,
                        )
                    )
                    if sa_obj.id != pos.id:
                        old_id = pos.id
                        pos.id = PositionId(sa_obj.id)
                        org.positions[pos.id] = pos
                        org.positions.pop(old_id, None)
                case PositionUpdated():
                    pos = org.positions.get(evt.payload["position_id"])  # type: ignore[index]
                    if pos is None:
                        continue
                    sa_org_type = self._to_sa_org_type(pos.org_type)
                    DbManager.update_record(
                        SAPosition,
                        pos.id,
                        {
                            SAPosition.name: pos.name.value,
                            SAPosition.description: pos.description,
                            SAPosition.org_type: sa_org_type,
                            SAPosition.org_id: org.id,
                        },
                    )
                case PositionDeleted():
                    # No soft-delete column on positions; best-effort: remove assignments for this position
                    pid = evt.payload["position_id"]  # type: ignore[index]
                    DbManager.delete_records(
                        SAPositionAssignment,
                        [SAPositionAssignment.org_id == org.id, SAPositionAssignment.position_id == int(pid)],
                    )

                # Assignments
                case PositionAssigned():
                    pid = int(evt.payload["position_id"])  # type: ignore[index]
                    uid = int(evt.payload["user_id"])  # type: ignore[index]
                    existing = DbManager.find_records(
                        SAPositionAssignment,
                        [
                            SAPositionAssignment.org_id == org.id,
                            SAPositionAssignment.position_id == pid,
                            SAPositionAssignment.user_id == uid,
                        ],
                    )
                    if not existing:
                        DbManager.create_record(SAPositionAssignment(org_id=org.id, position_id=pid, user_id=uid))
                case PositionUnassigned():
                    pid = int(evt.payload["position_id"])  # type: ignore[index]
                    uid = int(evt.payload["user_id"])  # type: ignore[index]
                    DbManager.delete_records(
                        SAPositionAssignment,
                        [
                            SAPositionAssignment.org_id == org.id,
                            SAPositionAssignment.position_id == pid,
                            SAPositionAssignment.user_id == uid,
                        ],
                    )

        # Clear processed domain events
        try:
            org._events.clear()  # type: ignore[attr-defined]
        except Exception:
            pass

    # --- Query helpers (DDD read adapters) ---
    def get_locations_and_event_types(
        self,
        org_id: OrgId,
        *,
        include_global_event_types: bool = True,
        only_active: bool = True,
    ) -> Tuple[List[Location], List[EventType]]:
        """Return (locations, event_types) for a region org.

        include_global_event_types: if True, prepend active global (specific_org_id NULL) event types.
        only_active: if True filter out inactive rows.
        Order: alphabetical by name.
        """
        # Locations tied to org_id
        loc_filters = [SALocation.org_id == int(org_id)]
        if only_active and hasattr(SALocation, "is_active"):
            loc_filters.append(SALocation.is_active.is_(True))  # type: ignore[attr-defined]
        sa_locs = DbManager.find_records(SALocation, loc_filters)
        locs: List[Location] = []
        for rec in sa_locs:
            raw_name = rec.name or ""
            display_name = (
                raw_name.strip()
                or (rec.description or rec.address_street or rec.address_city or rec.address_state or rec.address_zip)
                or "Unnamed Location"
            )
            locs.append(
                Location(
                    id=LocationId(rec.id),
                    name=LocationName(display_name),
                    description=rec.description,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    address_street=rec.address_street,
                    address_street2=rec.address_street2,
                    address_city=rec.address_city,
                    address_state=rec.address_state,
                    address_zip=rec.address_zip,
                    address_country=rec.address_country,
                    is_active=rec.is_active,
                    legacy_blank_name=(raw_name.strip() == ""),
                )
            )
        # Event types: custom + optional globals
        et_filters = [SAEventType.specific_org_id == int(org_id)]
        if only_active and hasattr(SAEventType, "is_active"):
            et_filters.append(SAEventType.is_active.is_(True))  # type: ignore[attr-defined]
        sa_custom_types = DbManager.find_records(SAEventType, et_filters)
        sa_global_types: List[SAEventType] = []
        if include_global_event_types:
            g_filters = [SAEventType.specific_org_id.is_(None)]
            if only_active and hasattr(SAEventType, "is_active"):
                g_filters.append(SAEventType.is_active.is_(True))  # type: ignore[attr-defined]
            sa_global_types = DbManager.find_records(SAEventType, g_filters)
        event_types: List[EventType] = []
        # First global, then custom (will sort later)
        for rec in list(sa_global_types) + list(sa_custom_types):
            event_types.append(
                EventType(
                    id=EventTypeId(rec.id),
                    name=EventTypeName(rec.name),
                    acronym=Acronym(rec.acronym or rec.name[:2]),
                    category=getattr(rec, "event_category", "first_f"),
                    is_active=getattr(rec, "is_active", True),
                )
            )
        # Sort alpha by name
        locs.sort(key=lambda loc: loc.name.value.lower())
        event_types.sort(key=lambda et: et.name.value.lower())
        return locs, event_types

    def get_locations(self, org_id: OrgId, *, only_active: bool = True) -> List[Location]:
        loc_filters = [SALocation.org_id == int(org_id)]
        if only_active and hasattr(SALocation, "is_active"):
            loc_filters.append(SALocation.is_active.is_(True))  # type: ignore[attr-defined]
        sa_locs = DbManager.find_records(SALocation, loc_filters)
        locs: List[Location] = []
        for rec in sa_locs:
            raw_name = rec.name or ""
            display_name = (
                raw_name.strip()
                or (rec.description or rec.address_street or rec.address_city or rec.address_state or rec.address_zip)
                or "Unnamed Location"
            )
            locs.append(
                Location(
                    id=LocationId(rec.id),
                    name=LocationName(display_name),
                    description=rec.description,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    address_street=rec.address_street,
                    address_street2=rec.address_street2,
                    address_city=rec.address_city,
                    address_state=rec.address_state,
                    address_zip=rec.address_zip,
                    address_country=rec.address_country,
                    is_active=rec.is_active,
                    legacy_blank_name=(raw_name.strip() == ""),
                )
            )
        locs.sort(key=lambda loc: loc.name.value.lower())
        return locs

    def get_event_types(
        self, org_id: OrgId, *, include_global: bool = True, only_active: bool = True
    ) -> List[EventType]:
        # Custom types
        filters = [SAEventType.specific_org_id == int(org_id)]
        if only_active and hasattr(SAEventType, "is_active"):
            filters.append(SAEventType.is_active.is_(True))  # type: ignore[attr-defined]
        custom = DbManager.find_records(SAEventType, filters)
        global_rows: List[SAEventType] = []
        if include_global:
            g_filters = [SAEventType.specific_org_id.is_(None)]
            if only_active and hasattr(SAEventType, "is_active"):
                g_filters.append(SAEventType.is_active.is_(True))  # type: ignore[attr-defined]
            global_rows = DbManager.find_records(SAEventType, g_filters)
        results: List[EventType] = []
        for rec in list(global_rows) + list(custom):
            results.append(
                EventType(
                    id=EventTypeId(rec.id),
                    name=EventTypeName(rec.name),
                    acronym=Acronym(rec.acronym or rec.name[:2]),
                    category=getattr(rec, "event_category", "first_f"),
                    is_active=getattr(rec, "is_active", True),
                )
            )
        results.sort(key=lambda et: et.name.value.lower())
        return results

    def get_event_tags(self, org_id: OrgId, *, include_global: bool = True, only_active: bool = True) -> List[EventTag]:
        # Custom tags
        filters = [SAEventTag.specific_org_id == int(org_id)]
        if only_active and hasattr(SAEventTag, "is_active"):
            filters.append(SAEventTag.is_active.is_(True))  # type: ignore[attr-defined]
        custom = DbManager.find_records(SAEventTag, filters)
        global_rows: List[SAEventTag] = []
        if include_global:
            g_filters = [SAEventTag.specific_org_id.is_(None)]
            if only_active and hasattr(SAEventTag, "is_active"):
                g_filters.append(SAEventTag.is_active.is_(True))  # type: ignore[attr-defined]
            global_rows = DbManager.find_records(SAEventTag, g_filters)
        results: List[EventTag] = []
        for rec in list(global_rows) + list(custom):
            results.append(
                EventTag(
                    id=EventTagId(rec.id),
                    name=EventTagName(rec.name),
                    color=getattr(rec, "color", "#000000"),
                    is_active=getattr(rec, "is_active", True),
                )
            )
        results.sort(key=lambda t: t.name.value.lower())
        return results

    def get_positions(self, org_id: OrgId, *, include_global: bool = True) -> List[Position]:
        # Custom positions
        custom = DbManager.find_records(SAPosition, [SAPosition.org_id == int(org_id)])
        global_rows: List[SAPosition] = []
        if include_global:
            global_rows = DbManager.find_records(SAPosition, [SAPosition.org_id.is_(None)])
        results: List[Position] = []
        for rec in list(global_rows) + list(custom):
            org_type_key: Optional[str] = None
            ot = getattr(rec, "org_type", None)
            if ot is not None:
                try:
                    org_type_key = str(ot.name).strip().lower()
                except Exception:
                    org_type_key = str(ot).strip().lower()
            results.append(
                Position(
                    id=PositionId(rec.id),
                    name=PositionName(rec.name),
                    org_type=org_type_key,
                    description=getattr(rec, "description", None),
                    is_active=True,
                )
            )
        results.sort(key=lambda p: p.name.value.lower())
        return results

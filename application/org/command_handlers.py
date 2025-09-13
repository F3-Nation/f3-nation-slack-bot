from __future__ import annotations

from domain.org.repository import OrgRepository
from domain.org.value_objects import EventTagId

from .commands import (
    AddEventTag,
    AddEventType,
    AddLocation,
    CloneGlobalEventTag,
    CloneGlobalEventType,
    CreateAo,
    DeactivateAo,
    SoftDeleteEventTag,
    SoftDeleteEventType,
    SoftDeleteLocation,
    UpdateAoProfile,
    UpdateEventTag,
    UpdateEventType,
    UpdateLocation,
    UpdateRegionProfile,
)


class OrgCommandHandler:
    def __init__(self, repo: OrgRepository):
        self.repo = repo

    def handle(self, command):  # naive dispatcher for now
        if isinstance(command, UpdateRegionProfile):
            return self._handle_update_region_profile(command)
        if isinstance(command, AddEventTag):
            return self._handle_add_event_tag(command)
        if isinstance(command, UpdateEventTag):
            return self._handle_update_event_tag(command)
        if isinstance(command, SoftDeleteEventTag):
            return self._handle_soft_delete_event_tag(command)
        if isinstance(command, CloneGlobalEventTag):
            return self._handle_clone_global_event_tag(command)
        if isinstance(command, AddEventType):
            return self._handle_add_event_type(command)
        if isinstance(command, UpdateEventType):
            return self._handle_update_event_type(command)
        if isinstance(command, SoftDeleteEventType):
            return self._handle_soft_delete_event_type(command)
        if isinstance(command, CloneGlobalEventType):
            return self._handle_clone_global_event_type(command)
        if isinstance(command, AddLocation):
            return self._handle_add_location(command)
        if isinstance(command, UpdateLocation):
            return self._handle_update_location(command)
        if isinstance(command, SoftDeleteLocation):
            return self._handle_soft_delete_location(command)
        if isinstance(command, CreateAo):
            return self._handle_create_ao(command)
        if isinstance(command, UpdateAoProfile):
            return self._handle_update_ao_profile(command)
        if isinstance(command, DeactivateAo):
            return self._handle_deactivate_ao(command)
        raise ValueError(f"Unhandled command type: {type(command)}")

    def _handle_update_region_profile(self, cmd: UpdateRegionProfile):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")

        # Sentinel value for unset fields
        SENTINEL = getattr(cmd, "SENTINEL", object())

        # Update fields only if not SENTINEL
        for attr in ["name", "description", "website", "email", "twitter", "facebook", "instagram", "logo_url"]:
            val = getattr(cmd, attr, SENTINEL)
            if val is not SENTINEL:
                setattr(org, attr, val)

        if getattr(cmd, "admin_user_ids", SENTINEL) is not SENTINEL:
            # Only replace if a non-None list is provided; empty list should still raise (domain rule)
            if cmd.admin_user_ids is not None:
                org.replace_admins([int(u) for u in cmd.admin_user_ids])

        org.version += 1
        self.repo.save(org)
        return org

    # --- Event Tag handlers ---
    def _handle_add_event_tag(self, cmd: AddEventTag):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.add_event_tag(name=cmd.name, color=cmd.color, triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_update_event_tag(self, cmd: UpdateEventTag):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.update_event_tag(EventTagId(cmd.tag_id), name=cmd.name, color=cmd.color, triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_soft_delete_event_tag(self, cmd: SoftDeleteEventTag):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.soft_delete_event_tag(EventTagId(cmd.tag_id), triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_clone_global_event_tag(self, cmd: CloneGlobalEventTag):
        # For now cloning just copies name/color from global row and adds as custom
        # We directly query underlying model to fetch global tag
        from f3_data_models.models import EventTag as ORMEventTag  # local import to avoid layering issues
        from f3_data_models.utils import DbManager

        global_tag = DbManager.get(ORMEventTag, cmd.global_tag_id)
        if not global_tag:
            raise ValueError("Global tag not found")
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.add_event_tag(name=global_tag.name, color=global_tag.color, triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    # --- Event Type handlers ---
    def _handle_add_event_type(self, cmd: AddEventType):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.add_event_type(name=cmd.name, category=cmd.category, acronym=cmd.acronym, triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_update_event_type(self, cmd: UpdateEventType):
        from domain.org.value_objects import EventTypeId

        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.update_event_type(
            EventTypeId(cmd.event_type_id),
            name=cmd.name,
            category=cmd.category,
            acronym=cmd.acronym,
            triggered_by=cmd.triggered_by,
        )
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_soft_delete_event_type(self, cmd: SoftDeleteEventType):
        from domain.org.value_objects import EventTypeId

        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.soft_delete_event_type(EventTypeId(cmd.event_type_id), triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_clone_global_event_type(self, cmd: CloneGlobalEventType):
        # Clone global (no specific_org_id) event type into org
        from f3_data_models.models import EventType as ORMEventType  # local import
        from f3_data_models.utils import DbManager

        global_et = DbManager.get(ORMEventType, cmd.global_event_type_id)
        if not global_et or global_et.specific_org_id is not None:
            raise ValueError("Global event type not found")
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.add_event_type(
            name=global_et.name,
            category=getattr(global_et, "event_category", "first_f"),
            acronym=global_et.acronym,
            triggered_by=cmd.triggered_by,
        )
        org.version += 1
        self.repo.save(org)
        return org

    # --- Location handlers ---
    def _handle_add_location(self, cmd: AddLocation):
        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.add_location(
            name=cmd.name,
            description=cmd.description,
            latitude=cmd.latitude,
            longitude=cmd.longitude,
            address_street=cmd.address_street,
            address_street2=cmd.address_street2,
            address_city=cmd.address_city,
            address_state=cmd.address_state,
            address_zip=cmd.address_zip,
            address_country=cmd.address_country,
            triggered_by=cmd.triggered_by,
        )
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_update_location(self, cmd: UpdateLocation):
        from domain.org.value_objects import LocationId

        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.update_location(
            LocationId(cmd.location_id),
            name=cmd.name,
            description=cmd.description,
            latitude=cmd.latitude,
            longitude=cmd.longitude,
            address_street=cmd.address_street,
            address_street2=cmd.address_street2,
            address_city=cmd.address_city,
            address_state=cmd.address_state,
            address_zip=cmd.address_zip,
            address_country=cmd.address_country,
            triggered_by=cmd.triggered_by,
        )
        org.version += 1
        self.repo.save(org)
        return org

    def _handle_soft_delete_location(self, cmd: SoftDeleteLocation):
        from domain.org.value_objects import LocationId

        org = self.repo.get(cmd.org_id)
        if not org:
            raise ValueError("Org not found")
        org.soft_delete_location(LocationId(cmd.location_id), triggered_by=cmd.triggered_by)
        org.version += 1
        self.repo.save(org)
        return org

    # --- AO (child org) handlers ---
    def _handle_create_ao(self, cmd: CreateAo):
        # Validate parent region exists
        region = self.repo.get(cmd.region_id)
        if not region or region.type != "region":
            raise ValueError("Region not found")
        # Name uniqueness within region: query children
        children = self.repo.list_children(cmd.region_id, include_inactive=False)
        if any(c.name.strip().lower() == cmd.name.strip().lower() for c in children):
            raise ValueError("Duplicate AO name in region")
        # Persist AO via underlying ORM for now
        from f3_data_models.models import Org as SAOrg  # type: ignore
        from f3_data_models.models import Org_Type
        from f3_data_models.utils import DbManager  # type: ignore

        meta = {"slack_channel_id": cmd.slack_channel_id} if cmd.slack_channel_id else {}
        sa = SAOrg(
            parent_id=int(region.id),
            org_type=Org_Type.ao,
            is_active=True,
            name=cmd.name,
            description=cmd.description,
            meta=meta or None,
            default_location_id=cmd.default_location_id,
            logo_url=cmd.logo_url,
        )
        DbManager.create_record(sa)
        # No change to region aggregate needed
        return sa.id

    def _handle_update_ao_profile(self, cmd: UpdateAoProfile):
        from f3_data_models.models import Org as SAOrg  # type: ignore
        from f3_data_models.utils import DbManager  # type: ignore

        # Minimal update; name uniqueness validation requires parent lookup
        sa_ao = DbManager.get(SAOrg, cmd.ao_id)
        if not sa_ao:
            raise ValueError("AO not found")
        fields = {}
        if cmd.name is not None:
            # enforce uniqueness within parent if present
            parent_id = sa_ao.parent_id
            if parent_id and cmd.name.strip():
                siblings = self.repo.list_children(parent_id, include_inactive=False)
                if any(c.id != cmd.ao_id and c.name.strip().lower() == cmd.name.strip().lower() for c in siblings):
                    raise ValueError("Duplicate AO name in region")
            fields[SAOrg.name] = cmd.name
        if cmd.description is not None:
            fields[SAOrg.description] = cmd.description
        if cmd.default_location_id is not None:
            fields[SAOrg.default_location_id] = cmd.default_location_id
        if cmd.slack_channel_id is not None:
            meta = dict(getattr(sa_ao, "meta", {}) or {})
            if cmd.slack_channel_id:
                meta["slack_channel_id"] = cmd.slack_channel_id
            fields[SAOrg.meta] = meta
        if cmd.logo_url is not None:
            fields[SAOrg.logo_url] = cmd.logo_url
        if fields:
            DbManager.update_record(SAOrg, cmd.ao_id, fields=fields)
        return True

    def _handle_deactivate_ao(self, cmd: DeactivateAo):
        import datetime as _dt

        from f3_data_models.models import Event, EventInstance  # type: ignore
        from f3_data_models.models import Org as SAOrg
        from f3_data_models.utils import DbManager  # type: ignore

        sa_ao = DbManager.get(SAOrg, cmd.ao_id)
        if not sa_ao:
            raise ValueError("AO not found")
        DbManager.update_record(SAOrg, cmd.ao_id, fields={SAOrg.is_active: False})
        DbManager.update_records(Event, [Event.org_id == cmd.ao_id], fields={Event.is_active: False})
        DbManager.update_records(
            EventInstance,
            [EventInstance.org_id == cmd.ao_id, EventInstance.start_date >= _dt.datetime.now()],
            fields={EventInstance.is_active: False},
        )
        return True

from __future__ import annotations

from domain.org.repository import OrgRepository
from domain.org.value_objects import EventTagId

from .commands import (
    AddEventTag,
    CloneGlobalEventTag,
    SoftDeleteEventTag,
    UpdateEventTag,
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
            org.replace_admins([int(u) for u in cmd.admin_user_ids] if cmd.admin_user_ids is not None else [])

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

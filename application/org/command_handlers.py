from __future__ import annotations

from domain.org.repository import OrgRepository

from .commands import UpdateRegionProfile


class OrgCommandHandler:
    def __init__(self, repo: OrgRepository):
        self.repo = repo

    def handle(self, command):  # naive dispatcher for now
        if isinstance(command, UpdateRegionProfile):
            return self._handle_update_region_profile(command)
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

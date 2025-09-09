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
        if cmd.name:
            org.name = cmd.name
        if cmd.description is not None:
            org.description = cmd.description
        org.version += 1
        self.repo.save(org)
        return org

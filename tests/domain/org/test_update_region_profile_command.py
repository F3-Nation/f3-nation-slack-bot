from application.org.command_handlers import OrgCommandHandler
from application.org.commands import UpdateRegionProfile
from domain.org.entities import Org
from domain.org.repository import OrgRepository
from domain.org.value_objects import OrgId


class InMemoryOrgRepo(OrgRepository):
    def __init__(self):
        self.store = {}

    def get(self, org_id: OrgId):
        return self.store.get(org_id)

    def save(self, org: Org):
        self.store[org.id] = org

    def list_children(self, parent_id, include_inactive: bool = False):  # type: ignore[override]
        return []

    # Minimal implementations to satisfy abstract interface for this unit test
    def get_locations(self, org_id, *, only_active: bool = True):  # type: ignore[override]
        org = self.store.get(org_id)
        if not org:
            return []
        return [l for l in org.locations.values() if (l.is_active or not only_active)]  # noqa: E741

    def get_event_types(self, org_id, *, include_global: bool = True, only_active: bool = True):  # type: ignore[override]
        org = self.store.get(org_id)
        if not org:
            return []
        return [et for et in org.event_types.values() if (et.is_active or not only_active)]

    def get_event_tags(self, org_id, *, include_global: bool = True, only_active: bool = True):  # type: ignore[override]
        org = self.store.get(org_id)
        if not org:
            return []
        return [t for t in org.event_tags.values() if (t.is_active or not only_active)]

    def get_positions(self, org_id, *, include_global: bool = True):  # type: ignore[override]
        org = self.store.get(org_id)
        if not org:
            return []
        return list(org.positions.values())


def test_update_region_profile():
    repo = InMemoryOrgRepo()
    org = Org(id=OrgId(1), parent_id=None, type="region", name="Old Name")
    repo.save(org)
    handler = OrgCommandHandler(repo)
    handler.handle(UpdateRegionProfile(org_id=OrgId(1), name="New Name", description="Desc"))
    updated = repo.get(OrgId(1))
    assert updated.name == "New Name"
    assert updated.description == "Desc"
    assert updated.version == 1

import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import UpdateRegionProfile
from domain.org.entities import Org
from domain.org.repository import OrgRepository
from domain.org.value_objects import OrgId


class FakeOrgRepo(OrgRepository):
    def __init__(self, org: Org):
        self._orgs = {int(org.id): org}

    def get(self, org_id):  # type: ignore[override]
        return self._orgs.get(int(org_id))

    def save(self, org):  # type: ignore[override]
        self._orgs[int(org.id)] = org

    def list_children(self, parent_id, include_inactive: bool = False):  # type: ignore[override]
        return []

    # Abstract query methods (not used in these tests but required)
    def get_locations(self, org_id, *, only_active: bool = True):  # type: ignore[override]
        org = self.get(org_id)
        if not org:
            return []
        return [loc for loc in org.locations.values() if (loc.is_active or not only_active)]

    def get_event_types(self, org_id, *, include_global: bool = True, only_active: bool = True):  # type: ignore[override]
        org = self.get(org_id)
        if not org:
            return []
        return [et for et in org.event_types.values() if (et.is_active or not only_active)]

    def get_event_tags(self, org_id, *, include_global: bool = True, only_active: bool = True):  # type: ignore[override]
        org = self.get(org_id)
        if not org:
            return []
        return [t for t in org.event_tags.values() if (t.is_active or not only_active)]

    def get_positions(self, org_id, *, include_global: bool = True):  # type: ignore[override]
        org = self.get(org_id)
        if not org:
            return []
        return list(org.positions.values())


def test_update_some_fields_only():
    org = Org(id=OrgId(50), parent_id=None, type="region", name="Initial")
    handler = OrgCommandHandler(FakeOrgRepo(org))
    # Only set name and website
    handler.handle(UpdateRegionProfile(org_id=50, name="Renamed", website="https://example.org"))
    updated = handler.repo.get(50)
    assert updated.name == "Renamed"
    assert updated.website == "https://example.org"
    assert updated.description is None  # untouched
    assert updated.version == 1


def test_replace_admins():
    org = Org(id=OrgId(51), parent_id=None, type="region", name="Org")
    org.assign_admin(1)
    handler = OrgCommandHandler(FakeOrgRepo(org))
    handler.handle(UpdateRegionProfile(org_id=51, admin_user_ids=[2, 3]))
    updated = handler.repo.get(51)
    assert updated.admin_user_ids == [2, 3]
    assert updated.version == 1


def test_replace_admins_requires_at_least_one():
    org = Org(id=OrgId(52), parent_id=None, type="region", name="Org")
    org.assign_admin(10)
    handler = OrgCommandHandler(FakeOrgRepo(org))
    with pytest.raises(ValueError):
        handler.handle(UpdateRegionProfile(org_id=52, admin_user_ids=[]))

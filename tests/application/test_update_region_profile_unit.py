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

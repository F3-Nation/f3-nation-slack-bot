import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddLocation, SoftDeleteLocation, UpdateLocation
from domain.org.entities import Org
from domain.org.repository import OrgRepository
from domain.org.value_objects import OrgId


class FakeOrgRepo(OrgRepository):
    def __init__(self, org: Org):
        self._orgs = {int(org.id): org}
        self.saved = 0

    def get(self, org_id):  # type: ignore[override]
        return self._orgs.get(int(org_id))

    def save(self, org):  # type: ignore[override]
        self._orgs[int(org.id)] = org
        self.saved += 1


@pytest.fixture()
def handler_and_repo():
    org = Org(id=OrgId(1), parent_id=None, type="region", name="TestOrg")
    repo = FakeOrgRepo(org)
    handler = OrgCommandHandler(repo)
    return handler, repo


def test_add_update_soft_delete_location_command(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(
        AddLocation(
            org_id=1,
            name="Main Park",
            description="At the flag",
            latitude=35.0,
            longitude=-80.0,
            address_street="123 Main St",
            address_city="CLT",
            address_state="NC",
            address_zip="28202",
            address_country="USA",
        )
    )
    org = repo.get(1)
    loc_id = next(iter(org.locations.keys()))
    handler.handle(UpdateLocation(org_id=1, location_id=int(loc_id), name="Main Park North"))
    org = repo.get(1)
    assert any(loc.name.value == "Main Park North" for loc in org.locations.values())
    handler.handle(SoftDeleteLocation(org_id=1, location_id=int(loc_id)))
    org = repo.get(1)
    assert not org.locations[loc_id].is_active
    assert org.version == 3  # add + update + delete


def test_duplicate_location_name_raises(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(AddLocation(org_id=1, name="DupPlace"))
    with pytest.raises(ValueError):
        handler.handle(AddLocation(org_id=1, name="DupPlace"))

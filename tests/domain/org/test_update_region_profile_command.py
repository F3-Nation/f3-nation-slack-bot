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

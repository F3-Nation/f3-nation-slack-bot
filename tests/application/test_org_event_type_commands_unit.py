import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddEventType, SoftDeleteEventType, UpdateEventType
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


@pytest.fixture()
def handler_and_repo():
    org = Org(id=OrgId(10), parent_id=None, type="region", name="TypeOrg")
    handler = OrgCommandHandler(FakeOrgRepo(org))
    return handler


def test_add_event_type(handler_and_repo):
    handler = handler_and_repo
    handler.handle(AddEventType(org_id=10, name="Bootcamp", category="first_f", acronym="BC"))
    org = handler.repo.get(10)
    assert len(org.event_types) == 1
    et = next(iter(org.event_types.values()))
    assert et.name.value == "Bootcamp"
    assert et.acronym.value == "BC"
    assert org.version == 1


def test_update_event_type(handler_and_repo):
    handler = handler_and_repo
    handler.handle(AddEventType(org_id=10, name="Ruck", category="first_f", acronym="RK"))
    org = handler.repo.get(10)
    et_id = next(iter(org.event_types.keys()))
    handler.handle(UpdateEventType(org_id=10, event_type_id=int(et_id), name="Ruck2", acronym="R2"))
    org = handler.repo.get(10)
    et = org.event_types[et_id]
    assert et.name.value == "Ruck2"
    assert et.acronym.value == "R2"
    assert org.version == 2


def test_soft_delete_event_type(handler_and_repo):
    handler = handler_and_repo
    handler.handle(AddEventType(org_id=10, name="Run", category="first_f", acronym="RN"))
    org = handler.repo.get(10)
    et_id = next(iter(org.event_types.keys()))
    handler.handle(SoftDeleteEventType(org_id=10, event_type_id=int(et_id)))
    org = handler.repo.get(10)
    assert not org.event_types[et_id].is_active
    assert org.version == 2


def test_duplicate_event_type_name(handler_and_repo):
    handler = handler_and_repo
    handler.handle(AddEventType(org_id=10, name="Bootcamp", category="first_f", acronym="BC"))
    with pytest.raises(ValueError):
        handler.handle(AddEventType(org_id=10, name="Bootcamp", category="first_f", acronym="BP"))


def test_duplicate_event_type_acronym(handler_and_repo):
    handler = handler_and_repo
    handler.handle(AddEventType(org_id=10, name="Bootcamp", category="first_f", acronym="BC"))
    with pytest.raises(ValueError):
        handler.handle(AddEventType(org_id=10, name="Bootcamp2", category="first_f", acronym="BC"))

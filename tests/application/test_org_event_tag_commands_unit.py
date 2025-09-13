import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddEventTag, SoftDeleteEventTag, UpdateEventTag
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
        # In-memory, just mark saved and keep reference
        self._orgs[int(org.id)] = org
        self.saved += 1


@pytest.fixture()
def handler_and_repo():
    org = Org(id=OrgId(1), parent_id=None, type="region", name="TestOrg")
    repo = FakeOrgRepo(org)
    handler = OrgCommandHandler(repo)
    return handler, repo


def test_add_event_tag_command(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(AddEventTag(org_id=1, name="CSAUP", color="red"))
    org = repo.get(1)
    assert len(org.event_tags) == 1
    tag = next(iter(org.event_tags.values()))
    assert tag.name.value == "CSAUP"
    assert tag.color == "red"
    assert org.version == 1
    # Domain event recorded
    assert any(e.__class__.__name__ == "EventTagCreated" for e in org.events)


def test_update_event_tag_command(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(AddEventTag(org_id=1, name="CSAUP", color="red"))
    org = repo.get(1)
    tag_id = next(iter(org.event_tags.keys()))
    handler.handle(UpdateEventTag(org_id=1, tag_id=int(tag_id), name="CSAUP2", color="blue"))
    org = repo.get(1)
    tag = org.event_tags[tag_id]
    assert tag.name.value == "CSAUP2"
    assert tag.color == "blue"
    assert org.version == 2  # add + update
    assert any(e.__class__.__name__ == "EventTagUpdated" for e in org.events)


def test_soft_delete_event_tag_command(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(AddEventTag(org_id=1, name="CSAUP", color="red"))
    org = repo.get(1)
    tag_id = next(iter(org.event_tags.keys()))
    handler.handle(SoftDeleteEventTag(org_id=1, tag_id=int(tag_id)))
    org = repo.get(1)
    assert not org.event_tags[tag_id].is_active
    assert org.version == 2  # add + delete
    assert any(e.__class__.__name__ == "EventTagDeleted" for e in org.events)


def test_duplicate_event_tag_name(handler_and_repo):
    handler, repo = handler_and_repo
    handler.handle(AddEventTag(org_id=1, name="CSAUP", color="red"))
    with pytest.raises(ValueError):
        handler.handle(AddEventTag(org_id=1, name="CSAUP", color="blue"))


def test_update_missing_tag_raises(handler_and_repo):
    handler, repo = handler_and_repo
    with pytest.raises(ValueError):
        handler.handle(UpdateEventTag(org_id=1, tag_id=999, name="X"))

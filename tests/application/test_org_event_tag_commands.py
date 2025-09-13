import os
import uuid

import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddEventTag, CloneGlobalEventTag, SoftDeleteEventTag, UpdateEventTag
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository

REQUIRED_DB_VARS = [
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
]


def _db_available():
    return all(os.environ.get(v) for v in REQUIRED_DB_VARS)


@pytest.fixture()
def org_id():
    val = os.environ.get("ORG_REPO_TEST_ORG_ID")
    if not val:
        pytest.skip("Skipping Org command integration tests (set ORG_REPO_TEST_ORG_ID to enable)")
    return int(val)


def test_add_update_soft_delete_event_tag_command(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    handler = OrgCommandHandler(SqlAlchemyOrgRepository())
    tag_name = f"CmdTag{uuid.uuid4().hex[:5]}"
    # add
    handler.handle(AddEventTag(org_id=org_id, name=tag_name, color="blue"))
    # update
    repo = SqlAlchemyOrgRepository()
    org = repo.get(org_id)
    tag = next(t for t in org.event_tags.values() if t.name.value == tag_name)
    handler.handle(UpdateEventTag(org_id=org_id, tag_id=int(tag.id), name=tag_name + "X", color="red"))
    # soft delete
    handler.handle(SoftDeleteEventTag(org_id=org_id, tag_id=int(tag.id)))
    # verify
    reloaded = repo.get(org_id)
    updated = next(t for t in reloaded.event_tags.values() if t.name.value.startswith(tag_name))
    assert not updated.is_active


def test_clone_global_event_tag_command(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    handler = OrgCommandHandler(SqlAlchemyOrgRepository())
    # pick any existing global tag (no specific_org_id). We'll grab first.
    from f3_data_models.models import EventTag as ORMEventTag
    from f3_data_models.utils import DbManager

    # choose a global tag name not already present in org
    repo = SqlAlchemyOrgRepository()
    org = repo.get(org_id)
    existing_names = {t.name.value for t in org.event_tags.values()}
    global_tag = next(
        (
            t
            for t in DbManager.find_records(ORMEventTag, [True])
            if t.specific_org_id is None and t.name not in existing_names
        ),
        None,
    )
    if not global_tag:
        pytest.skip("No suitable global event tag available to clone")
    handler.handle(CloneGlobalEventTag(org_id=org_id, global_tag_id=global_tag.id))
    # verify tag with same name now exists for org
    repo = SqlAlchemyOrgRepository()
    org = repo.get(org_id)
    assert any(t.name.value == global_tag.name for t in org.event_tags.values())


def test_duplicate_event_tag_name_error(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    handler = OrgCommandHandler(SqlAlchemyOrgRepository())
    dup_name = f"DupTag{uuid.uuid4().hex[:4]}"
    handler.handle(AddEventTag(org_id=org_id, name=dup_name, color="green"))
    with pytest.raises(ValueError):
        handler.handle(AddEventTag(org_id=org_id, name=dup_name, color="red"))

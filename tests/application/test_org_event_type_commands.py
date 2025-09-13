import os
import uuid

import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddEventType, SoftDeleteEventType, UpdateEventType
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
        pytest.skip("Skipping event type command integration tests (set ORG_REPO_TEST_ORG_ID to enable)")
    return int(val)


def test_add_update_soft_delete_event_type_command(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    handler = OrgCommandHandler(SqlAlchemyOrgRepository())
    et_name = f"CmdType{uuid.uuid4().hex[:5]}"
    handler.handle(AddEventType(org_id=org_id, name=et_name, category="first_f", acronym=None))
    repo = SqlAlchemyOrgRepository()
    org = repo.get(org_id)
    et = next(t for t in org.event_types.values() if t.name.value == et_name)
    handler.handle(UpdateEventType(org_id=org_id, event_type_id=int(et.id), name=et_name + "X", acronym="CX"))
    handler.handle(SoftDeleteEventType(org_id=org_id, event_type_id=int(et.id)))
    reloaded = repo.get(org_id)
    stored = next(t for t in reloaded.event_types.values() if t.name.value.startswith(et_name))
    assert not stored.is_active


def test_duplicate_event_type_name_error(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    dup = f"DupType{uuid.uuid4().hex[:4]}"
    # choose a unique 2-char acronym
    existing_acros = {et.acronym.value for et in repo.get(org_id).event_types.values()}
    base = uuid.uuid4().hex.upper()
    acro1 = None
    for i in range(0, len(base) - 1, 2):
        cand = base[i : i + 2]
        if cand not in existing_acros:
            acro1 = cand
            break
    if acro1 is None:
        acro1 = "ZZ"
    handler.handle(AddEventType(org_id=org_id, name=dup, category="first_f", acronym=acro1))
    with pytest.raises(ValueError):
        handler.handle(AddEventType(org_id=org_id, name=dup, category="first_f", acronym="AA"))


def test_duplicate_event_type_acronym_error(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)
    name1 = f"Name{uuid.uuid4().hex[:4]}"
    name2 = f"Name{uuid.uuid4().hex[:4]}"
    # pick a unique acronym, then reuse it to trigger error
    existing_acros = {et.acronym.value for et in repo.get(org_id).event_types.values()}
    base = uuid.uuid4().hex.upper()
    acro = None
    for i in range(0, len(base) - 1, 2):
        cand = base[i : i + 2]
        if cand not in existing_acros:
            acro = cand
            break
    if acro is None:
        acro = "YY"
    handler.handle(AddEventType(org_id=org_id, name=name1, category="first_f", acronym=acro))
    with pytest.raises(ValueError):
        handler.handle(AddEventType(org_id=org_id, name=name2, category="first_f", acronym=acro))

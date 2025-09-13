import os
import uuid

import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddLocation, SoftDeleteLocation, UpdateLocation
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
        pytest.skip("Skipping location command integration tests (set ORG_REPO_TEST_ORG_ID to enable)")
    return int(val)


def test_add_update_soft_delete_location_command(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    handler = OrgCommandHandler(SqlAlchemyOrgRepository())
    name = f"Loc-{uuid.uuid4().hex[:6]}"
    handler.handle(AddLocation(org_id=org_id, name=name, latitude=35.1, longitude=-80.1))
    repo = SqlAlchemyOrgRepository()
    org = repo.get(org_id)
    loc = next(loc for loc in org.locations.values() if loc.name.value == name)
    handler.handle(UpdateLocation(org_id=org_id, location_id=int(loc.id), name=name + "X"))
    handler.handle(SoftDeleteLocation(org_id=org_id, location_id=int(loc.id)))
    reloaded = repo.get(org_id)
    stored = next(loc for loc in reloaded.locations.values() if loc.name.value.startswith(name))
    assert not stored.is_active

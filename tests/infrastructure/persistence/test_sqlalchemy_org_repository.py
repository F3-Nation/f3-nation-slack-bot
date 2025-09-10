import os
import uuid

import pytest

REQUIRED_DB_VARS = [
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_DB",
]


def _db_available():
    return all(os.environ.get(v) for v in REQUIRED_DB_VARS)


if _db_available():  # import only if DB configured
    from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository  # pragma: no cover
else:  # pragma: no cover
    SqlAlchemyOrgRepository = None  # type: ignore


@pytest.fixture()
def org_id():
    val = os.environ.get("ORG_REPO_TEST_ORG_ID")
    if not val:
        pytest.skip("Skipping SqlAlchemyOrgRepository integration tests (set ORG_REPO_TEST_ORG_ID to enable)")
    try:
        return int(val)
    except ValueError:  # pragma: no cover
        pytest.skip("ORG_REPO_TEST_ORG_ID must be an integer")


def test_repository_load_and_update(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()  # type: ignore
    org = repo.get(org_id)
    assert org is not None, "Expected existing Org for provided ORG_REPO_TEST_ORG_ID"
    original_name = org.name
    new_name = f"{original_name}-ut-{uuid.uuid4().hex[:6]}"
    org.name = new_name
    repo.save(org)

    # reload and verify persistence
    reloaded = repo.get(org_id)
    assert reloaded.name == new_name


def test_repository_add_event_type(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()  # type: ignore
    org = repo.get(org_id)
    assert org is not None
    before_count = len(org.event_types)
    et_name = f"TestType{uuid.uuid4().hex[:4]}"
    org.add_event_type(name=et_name, category="first_f", acronym=None, triggered_by=None)
    repo.save(org)
    reloaded = repo.get(org_id)
    assert len(reloaded.event_types) == before_count + 1
    assert any(et.name.value == et_name for et in reloaded.event_types.values())

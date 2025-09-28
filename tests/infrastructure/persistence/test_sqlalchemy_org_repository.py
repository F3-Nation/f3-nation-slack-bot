import os
import uuid

import pytest

REQUIRED_DB_VARS = [
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    # "DATABASE_DB",
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
    # org.name = new_name
    org.update_profile(name=new_name, triggered_by=None)
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
    # ensure acronym won't collide with existing ones
    existing_acros = {et.acronym.value for et in org.event_types.values()}
    base = uuid.uuid4().hex.upper()
    acro = None
    for i in range(0, len(base) - 1, 2):
        cand = base[i : i + 2]
        if cand not in existing_acros:
            acro = cand
            break
    if acro is None:
        acro = "ZX"
    org.add_event_type(name=et_name, category="first_f", acronym=acro, triggered_by=None)
    repo.save(org)
    reloaded = repo.get(org_id)
    assert len(reloaded.event_types) == before_count + 1
    assert any(et.name.value == et_name for et in reloaded.event_types.values())


def test_repository_add_event_tag(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()  # type: ignore
    org = repo.get(org_id)
    assert org is not None
    before_count = len(org.event_tags)
    tag_name = f"Tag{uuid.uuid4().hex[:4]}"
    org.add_event_tag(name=tag_name, color="blue", triggered_by=None)
    repo.save(org)
    reloaded = repo.get(org_id)
    assert len(reloaded.event_tags) == before_count + 1
    assert any(t.name.value == tag_name for t in reloaded.event_tags.values())


def test_repository_update_and_soft_delete_event_tag(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()  # type: ignore
    org = repo.get(org_id)
    assert org is not None
    # add tag
    tag_name = f"TmpTag{uuid.uuid4().hex[:4]}"
    tag = org.add_event_tag(name=tag_name, color="green", triggered_by=None)
    repo.save(org)
    # update
    org.update_event_tag(tag.id, name=tag_name + "X", color="red", triggered_by=None)
    repo.save(org)
    # soft delete
    org.soft_delete_event_tag(tag.id, triggered_by=None)
    repo.save(org)
    reloaded = repo.get(org_id)
    stored_tag = next(t for t in reloaded.event_tags.values() if t.name.value.startswith(tag_name))
    # After soft delete we keep record but inactive
    assert not stored_tag.is_active


def test_repository_add_update_soft_delete_location(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    repo = SqlAlchemyOrgRepository()  # type: ignore
    org = repo.get(org_id)
    assert org is not None
    before_count = len(org.locations)
    name = f"Loc{uuid.uuid4().hex[:4]}"
    loc = org.add_location(name=name, description="desc", latitude=1.23, longitude=4.56, triggered_by=None)
    repo.save(org)
    # update
    org.update_location(loc.id, name=name + "X", triggered_by=None)
    repo.save(org)
    # soft delete
    org.soft_delete_location(loc.id, triggered_by=None)
    repo.save(org)
    reloaded = repo.get(org_id)
    assert len(reloaded.locations) == before_count + 1
    stored = next(loc for loc in reloaded.locations.values() if loc.name.value.startswith(name))
    assert not stored.is_active


def test_list_children_and_create_deactivate_ao(org_id):
    if not _db_available():
        pytest.skip("Database env vars not set; skipping integration test")
    # list children before
    repo = SqlAlchemyOrgRepository()  # type: ignore
    before = repo.list_children(org_id)
    from application.org.command_handlers import OrgCommandHandler
    from application.org.commands import CreateAo, DeactivateAo

    handler = OrgCommandHandler(repo)
    base = f"AO-{uuid.uuid4().hex[:6]}"
    ao_id = handler.handle(CreateAo(region_id=org_id, name=base))
    after = repo.list_children(org_id)
    assert len(after) == len(before) + 1
    # deactivate newly created
    handler.handle(DeactivateAo(ao_id=int(ao_id)))
    # list_children filters to active only, so count should return to previous value
    after2 = repo.list_children(org_id)
    assert len(after2) == len(before)

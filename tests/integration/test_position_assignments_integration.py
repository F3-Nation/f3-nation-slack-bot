import os

import pytest

from application.org.command_handlers import OrgCommandHandler
from application.org.commands import AddPosition, ReplacePositionAssignments
from domain.org.value_objects import OrgId
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository

REQUIRED_DB_VARS = [
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
]


def _db_available() -> bool:
    return all(os.environ.get(v) for v in REQUIRED_DB_VARS)


def _get_test_org_id() -> int | None:
    val = os.environ.get("ORG_REPO_TEST_ORG_ID")
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


@pytest.mark.integration
@pytest.mark.skipif(not _db_available() or _get_test_org_id() is None, reason="DB or test org not configured")
def test_position_assignment_round_trip(monkeypatch):
    """Full flow: load org, add position, persist, reload, assign users, persist, reload, replace assignments."""
    org_id = _get_test_org_id()
    assert org_id is not None

    repo = SqlAlchemyOrgRepository()
    handler = OrgCommandHandler(repo)

    # Load baseline aggregate
    org = repo.get(OrgId(org_id))
    assert org is not None

    # Add a new custom position (unique name)
    position_name = "Integration Test Position"
    # Avoid naming collisions: if exists, append suffix
    existing_names = {p.name.value.lower() for p in org.positions.values()}
    suffix = 1
    base_name = position_name
    while position_name.lower() in existing_names:
        position_name = f"{base_name} {suffix}"
        suffix += 1
    handler.handle(
        AddPosition(
            org_id=org_id,
            name=position_name,
            description="Test position for integration assignment flow",
            org_type=None,
        )
    )

    # Reload and find new position id
    org_after_add = repo.get(OrgId(org_id))
    assert any(p.name.value == position_name for p in org_after_add.positions.values())
    pos_id = next(pid for pid, p in org_after_add.positions.items() if p.name.value == position_name)

    # Replace assignments with two user IDs (pick arbitrary integers unlikely to matter)
    handler.handle(
        ReplacePositionAssignments(
            org_id=org_id,
            position_id=int(pos_id),  # value object is int convertible
            user_ids=[99990001, 99990002],
        )
    )

    # Reload and assert assignments persisted
    org_after_assign = repo.get(OrgId(org_id))
    assigned_set = org_after_assign.position_assignments.get(pos_id, set())
    # The repository currently persists after save(); we need to call save via handler wrappers for assignments
    # If assignments not present yet, that's a failure
    assert {int(u) for u in assigned_set} == {99990001, 99990002}

    # Replace with single user
    handler.handle(
        ReplacePositionAssignments(
            org_id=org_id,
            position_id=int(pos_id),
            user_ids=[99990003],
        )
    )
    org_after_replace = repo.get(OrgId(org_id))
    assigned_set2 = org_after_replace.position_assignments.get(pos_id, set())
    assert {int(u) for u in assigned_set2} == {99990003}

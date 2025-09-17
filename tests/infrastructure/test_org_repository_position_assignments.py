from domain.org.entities import Org
from domain.org.value_objects import OrgId, UserId
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository


class DummyRepo(SqlAlchemyOrgRepository):
    """A thin subclass so we could monkeypatch DB calls in future if needed."""

    pass


def test_repository_assignment_methods_exist():
    dr = DummyRepo()
    assert hasattr(dr, "get")
    assert hasattr(dr, "save")


def test_org_replace_assignments_in_memory_flow(monkeypatch):
    # This test exercises domain + repository save path enough to ensure no attribute errors
    # without requiring a real database (DbManager interactions would occur in save; we don't run them here).
    org = Org(id=OrgId(80), parent_id=None, type="region", name="R80").rebuild_indexes()
    org.set_global_catalog()
    pos = org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)

    # Simulate existing assignments in aggregate
    org.assign_user_to_position(pos.id, UserId(1))
    org.assign_user_to_position(pos.id, UserId(2))

    # Replace with 2 + 3
    org.replace_position_assignments(pos.id, [UserId(2), UserId(3)])
    assert org.position_assignments[pos.id] == {UserId(2), UserId(3)}

    # Events: initial assign adds 1 & 2; replace removes 1 (unassigned) and adds 3 (assigned)
    # => total assigned events 3, unassigned events 1
    assigned = [e for e in org.events if e.__class__.__name__ == "PositionAssigned"]
    unassigned = [e for e in org.events if e.__class__.__name__ == "PositionUnassigned"]
    assert len(assigned) == 3
    assert len(unassigned) == 1

    # We don't call repo.save(org) to avoid DB dependency; structural domain test only.

from domain.org.entities import Org
from domain.org.value_objects import OrgId, UserId


def test_assign_and_unassign_user_to_position_events():
    org = Org(id=OrgId(70), parent_id=None, type="region", name="R70").rebuild_indexes()
    org.set_global_catalog()
    pos = org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)

    # Assign two users
    org.assign_user_to_position(pos.id, UserId(1))
    org.assign_user_to_position(pos.id, UserId(2))
    # Idempotent reassign
    org.assign_user_to_position(pos.id, UserId(1))

    assert org.position_assignments[pos.id] == {UserId(1), UserId(2)}
    # Two PositionAssigned events (idempotent second assign doesn't add)
    assigned_events = [e for e in org.events if e.__class__.__name__ == "PositionAssigned"]
    assert len(assigned_events) == 2

    # Unassign one
    org.unassign_user_from_position(pos.id, UserId(1))
    # Idempotent unassign
    org.unassign_user_from_position(pos.id, UserId(1))

    assert org.position_assignments[pos.id] == {UserId(2)}
    unassigned_events = [e for e in org.events if e.__class__.__name__ == "PositionUnassigned"]
    assert len(unassigned_events) == 1


def test_replace_position_assignments_add_and_remove():
    org = Org(id=OrgId(71), parent_id=None, type="region", name="R71").rebuild_indexes()
    pos = org.add_position(name="Weasel Shaker", description=None, org_type=None, triggered_by=None)

    # Initial replace with users 1,2
    org.replace_position_assignments(pos.id, [UserId(1), UserId(2)])
    assert org.position_assignments[pos.id] == {UserId(1), UserId(2)}

    # Replace with 2,3 (removes 1, adds 3)
    org.replace_position_assignments(pos.id, [UserId(2), UserId(3)])
    assert org.position_assignments[pos.id] == {UserId(2), UserId(3)}

    assigned_events = [e for e in org.events if e.__class__.__name__ == "PositionAssigned"]
    unassigned_events = [e for e in org.events if e.__class__.__name__ == "PositionUnassigned"]

    # Events breakdown:
    #   first replace adds 1,2 (2 assigned)
    #   second replace removes 1 (1 unassigned) and adds 3 (1 assigned)
    # => total assigned 3, unassigned 1
    assert len(assigned_events) == 3
    assert len(unassigned_events) == 1


def test_replace_position_assignments_clear_all():
    org = Org(id=OrgId(72), parent_id=None, type="region", name="R72").rebuild_indexes()
    pos = org.add_position(name="Sector Q", description=None, org_type=None, triggered_by=None)
    org.replace_position_assignments(pos.id, [UserId(10), UserId(11)])
    assert org.position_assignments[pos.id] == {UserId(10), UserId(11)}

    # Clear
    org.replace_position_assignments(pos.id, [])
    assert org.position_assignments.get(pos.id, set()) == set()
    assigned_events = [e for e in org.events if e.__class__.__name__ == "PositionAssigned"]
    unassigned_events = [e for e in org.events if e.__class__.__name__ == "PositionUnassigned"]
    # First replace adds 2 assigned events; second replace removes 2 -> total assigned 2, unassigned 2
    assert len(assigned_events) == 2
    assert len(unassigned_events) == 2

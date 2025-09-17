from domain.org.entities import Org
from domain.org.value_objects import OrgId


def test_position_conflicts_with_global_names_same_org_type():
    org = Org(id=OrgId(50), parent_id=None, type="region", name="R50").rebuild_indexes()
    # Simulate global catalog with positions
    org.set_global_catalog(position_names_by_type={None: {"nantan"}, "region": {"weasel_shaker"}})

    # Conflict with wildcard None scope
    try:
        org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)
        raise AssertionError("Expected duplicate position name (global wildcard)")
    except ValueError:
        pass

    # Conflict with matching org_type scope
    try:
        org.add_position(name="Weasel Shaker", description=None, org_type="region", triggered_by=None)
        raise AssertionError("Expected duplicate position name (global org_type)")
    except ValueError:
        pass

    # Bypass allowed for clone
    org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None, allow_global_duplicate=True)


def test_position_unique_per_org_type_including_wildcard():
    org = Org(id=OrgId(51), parent_id=None, type="region", name="R51").rebuild_indexes()
    # Add first position with wildcard None
    org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)
    # Adding same name for specific org_type should conflict due to wildcard coverage
    try:
        org.add_position(name="Nantan", description=None, org_type="region", triggered_by=None)
        raise AssertionError("Expected duplicate due to wildcard None position already present")
    except ValueError:
        pass

    # Adding different name for specific org_type works
    org.add_position(name="Weasel Shaker", description=None, org_type="region", triggered_by=None)

    # Adding same name but different specific org_type is allowed
    org.add_position(name="Weasel Shaker", description=None, org_type="sector", triggered_by=None)


def test_position_update_checks_conflicts():
    org = Org(id=OrgId(52), parent_id=None, type="region", name="R52").rebuild_indexes()
    org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)
    p2 = org.add_position(name="Weasel Shaker", description=None, org_type="region", triggered_by=None)
    # Attempt to rename p2 to Nantan should fail (wildcard conflict)
    try:
        org.update_position(p2.id, name="Nantan", description=None, org_type="region", triggered_by=None)
        raise AssertionError("Expected duplicate when renaming to existing wildcard position name")
    except ValueError:
        pass
    # Renaming p2 to same name different case is allowed (no change)
    org.update_position(p2.id, name="Weasel Shaker", description=None, org_type="region", triggered_by=None)

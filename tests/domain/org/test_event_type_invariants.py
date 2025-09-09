from domain.org.entities import Org
from domain.org.value_objects import OrgId


def test_add_event_type_uniqueness():
    org = Org(id=OrgId(1), parent_id=None, type="region", name="Test Region")
    org.add_event_type(name="Bootcamp", category="first_f", acronym="BC", triggered_by=None)
    try:
        org.add_event_type(name="Bootcamp", category="first_f", acronym="BO", triggered_by=None)
        raise AssertionError("Expected duplicate name error")
    except ValueError:
        pass


def test_cannot_remove_last_admin():
    org = Org(id=OrgId(1), parent_id=None, type="region", name="Test Region")
    org.assign_admin(user_id=1)
    try:
        org.revoke_admin(user_id=1)
        raise AssertionError("Expected cannot remove last admin")
    except ValueError:
        pass

from domain.org.entities import Org
from domain.org.value_objects import OrgId


def test_add_event_tag_uniqueness():
    org = Org(id=OrgId(2), parent_id=None, type="region", name="R2")
    org.add_event_tag(name="Convergence", color="red", triggered_by=None)
    try:
        org.add_event_tag(name="Convergence", color="blue", triggered_by=None)
        raise AssertionError("Expected duplicate event tag name error")
    except ValueError:
        pass


def test_soft_delete_event_tag():
    org = Org(id=OrgId(3), parent_id=None, type="region", name="R3")
    tag = org.add_event_tag(name="CSAUP", color="green", triggered_by=None)
    org.soft_delete_event_tag(tag.id, triggered_by=None)
    assert not org.event_tags[tag.id].is_active

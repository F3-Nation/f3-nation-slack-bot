from domain.org.entities import Org
from domain.org.value_objects import OrgId


def test_event_tag_conflicts_with_global_names():
    org = Org(id=OrgId(10), parent_id=None, type="region", name="R10").rebuild_indexes()
    # Simulate global catalog
    org.set_global_catalog(event_tag_names={"csaup", "convergence"})
    # Local name unique but collides with global
    try:
        org.add_event_tag(name="Convergence", color="red", triggered_by=None)
        raise AssertionError("Expected duplicate event tag name (global)")
    except ValueError:
        pass
    # Bypass is allowed for clones
    org.add_event_tag(name="Convergence", color="red", triggered_by=None, allow_global_duplicate=True)


def test_event_type_conflicts_with_global_names_and_acronyms():
    org = Org(id=OrgId(11), parent_id=None, type="region", name="R11").rebuild_indexes()
    org.set_global_catalog(event_type_names={"bootcamp"}, event_type_acronyms={"BC"})

    # Name conflict against global
    try:
        org.add_event_type(name="Bootcamp", category="first_f", acronym="BQ", triggered_by=None)
        raise AssertionError("Expected duplicate event type name (global)")
    except ValueError:
        pass

    # Acronym conflict against global
    try:
        org.add_event_type(name="Beatdown", category="first_f", acronym="BC", triggered_by=None)
        raise AssertionError("Expected duplicate event type acronym (global)")
    except ValueError:
        pass

    # Bypass for clone
    org.add_event_type(
        name="Bootcamp",
        category="first_f",
        acronym="BC",
        triggered_by=None,
        allow_global_duplicate=True,
    )

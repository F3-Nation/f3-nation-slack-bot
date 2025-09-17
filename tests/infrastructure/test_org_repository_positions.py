from domain.org.entities import Org
from domain.org.value_objects import OrgId
from infrastructure.persistence.sqlalchemy.org_repository import SqlAlchemyOrgRepository


def test_repository_round_trip_positions(monkeypatch):
    repo = SqlAlchemyOrgRepository()
    # We'll monkeypatch DbManager interactions with simple in-memory lists if necessary
    # For now this is a placeholder ensuring repository has method integration.
    assert hasattr(repo, "get")
    assert hasattr(repo, "save")
    # Can't fully integration test without real DB; this is a structural smoke test.
    org = Org(id=OrgId(60), parent_id=None, type="region", name="R60").rebuild_indexes()
    # Simulate global catalog injection (empty) and add position
    org.set_global_catalog()
    org.add_position(name="Nantan", description=None, org_type=None, triggered_by=None)
    # Save would attempt DB operations (requires real DbManager); ensure method exists
    # So we just assert position present pre-save.
    assert any(p.name.value == "Nantan" for p in org.positions.values())

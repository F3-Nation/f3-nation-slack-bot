import os
import sys

import pytest  # type: ignore

# Make repo root importable in tests
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Optional DB cleanup for integration tests that use a shared test org
# This helps avoid conflicts from previous runs by removing org-specific
# EventTypes/EventTags created by tests.

REQUIRED_DB_VARS = [
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
]


def _db_available() -> bool:
    return all(os.environ.get(v) for v in REQUIRED_DB_VARS)


def _list_org_specific_ids(org_id: int):
    """Return (event_type_ids, event_tag_ids, location_ids) for org rows."""
    try:
        from f3_data_models.models import EventTag as ORMEventTag  # type: ignore
        from f3_data_models.models import EventType as ORMEventType
        from f3_data_models.models import Location as ORMLocation  # type: ignore
        from f3_data_models.utils import DbManager  # type: ignore
    except Exception:
        return set(), set(), set()

    try:
        et_records = DbManager.find_records(ORMEventType, [ORMEventType.specific_org_id == org_id])
        tag_records = DbManager.find_records(ORMEventTag, [ORMEventTag.specific_org_id == org_id])
        loc_records = DbManager.find_records(ORMLocation, [ORMLocation.org_id == org_id])
    except Exception:
        return set(), set(), set()

    et_ids = {r.id for r in et_records}
    tag_ids = {r.id for r in tag_records}
    loc_ids = {r.id for r in loc_records}
    return et_ids, tag_ids, loc_ids


def _list_org_positions(org_id: int):
    """Return set of position IDs for a given org_id."""
    try:
        from f3_data_models.models import Position as ORMPosition  # type: ignore
        from f3_data_models.utils import DbManager  # type: ignore
    except Exception:
        return set()
    try:
        records = DbManager.find_records(ORMPosition, [ORMPosition.org_id == org_id])
    except Exception:
        return set()
    return {r.id for r in records}


@pytest.fixture(autouse=True)
def cleanup_test_org_function():
    """
    Per-test teardown: snapshot org-specific EventType/EventTag IDs before each test
    and delete any newly-created rows afterward. Enabled only when DB and
    ORG_REPO_TEST_ORG_ID are configured.
    """
    if not _db_available():
        yield
        return
    org_val = os.environ.get("ORG_REPO_TEST_ORG_ID")
    if not org_val:
        yield
        return
    try:
        org_id = int(org_val)
    except ValueError:
        yield
        return

    before_types, before_tags, before_locs = _list_org_specific_ids(org_id)
    before_positions = _list_org_positions(org_id)
    yield
    after_types, after_tags, after_locs = _list_org_specific_ids(org_id)
    after_positions = _list_org_positions(org_id)

    new_type_ids = after_types - before_types
    new_tag_ids = after_tags - before_tags
    new_loc_ids = after_locs - before_locs
    new_position_ids = after_positions - before_positions

    # Best-effort deletion of newly created rows
    try:
        from f3_data_models.models import EventTag as ORMEventTag  # type: ignore
        from f3_data_models.models import EventType as ORMEventType
        from f3_data_models.models import Location as ORMLocation  # type: ignore
        from f3_data_models.models import Position as ORMPosition  # type: ignore
        from f3_data_models.models import Position_x_Org_x_User as ORMAssignment  # type: ignore
        from f3_data_models.utils import DbManager  # type: ignore
    except Exception:
        return

    # Delete event types first (order is arbitrary here, but consistent)
    for et_id in new_type_ids:
        try:
            DbManager.delete_record(ORMEventType, et_id)
        except Exception:
            pass
    for tag_id in new_tag_ids:
        try:
            DbManager.delete_record(ORMEventTag, tag_id)
        except Exception:
            pass
    for loc_id in new_loc_ids:
        try:
            DbManager.delete_record(ORMLocation, loc_id)
        except Exception:
            pass
    # Delete assignments, then positions
    for pos_id in new_position_ids:
        try:
            DbManager.delete_records(ORMAssignment, [ORMAssignment.position_id == pos_id])
        except Exception:
            pass
    for pos_id in new_position_ids:
        try:
            DbManager.delete_record(ORMPosition, pos_id)
        except Exception:
            pass

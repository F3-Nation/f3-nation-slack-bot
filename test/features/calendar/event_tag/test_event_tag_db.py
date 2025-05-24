from unittest.mock import MagicMock, patch

from features.calendar.event_tag import event_tag_db


# Test get_all_event_tags
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_get_all_event_tags(mock_db):
    mock_db.find_records.return_value = ["tag1", "tag2"]
    result = event_tag_db.EventTagDB.get_all_event_tags()
    mock_db.find_records.assert_called_once()
    assert result == ["tag1", "tag2"]


# Test get_org_record
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_get_org_record(mock_db):
    mock_db.get.return_value = "org"
    result = event_tag_db.EventTagDB.get_org_record(123)
    mock_db.get.assert_called_once_with(event_tag_db.Org, 123, joinedloads="all")
    assert result == "org"


# Test get_event_tag
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_get_event_tag(mock_db):
    mock_db.get.return_value = "tag"
    result = event_tag_db.EventTagDB.get_event_tag(5)
    mock_db.get.assert_called_once_with(event_tag_db.EventTag, 5)
    assert result == "tag"


# Test create_event_tag
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_create_event_tag(mock_db):
    tag = MagicMock()
    event_tag_db.EventTagDB.create_event_tag(tag)
    mock_db.create_record.assert_called_once_with(tag)


# Test update_event_tag
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_update_event_tag(mock_db):
    event_tag_db.EventTagDB.update_event_tag(1, "name", "color")
    mock_db.update_record.assert_called_once_with(
        event_tag_db.EventTag, 1, {event_tag_db.EventTag.color: "color", event_tag_db.EventTag.name: "name"}
    )


# Test delete_event_tag
@patch("features.calendar.event_tag.event_tag_db.DbManager")
def test_delete_event_tag(mock_db):
    event_tag_db.EventTagDB.delete_event_tag(7)
    mock_db.delete_record.assert_called_once_with(event_tag_db.EventTag, 7)

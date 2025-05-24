from unittest.mock import MagicMock, patch

import pytest

from features.calendar.event_tag import event_tag


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def mock_context():
    return {}


@pytest.fixture
def mock_region_record():
    mock = MagicMock()
    mock.org_id = 123
    return mock


@patch("features.calendar.event_tag.event_tag.safe_get")
@patch("features.calendar.event_tag.event_tag.EventTagService")
def test_manage_event_tags_add(mock_service, mock_safe_get, mock_client, mock_logger, mock_context, mock_region_record):
    body = {"actions": [{"selected_option": {"value": "add"}}]}
    mock_safe_get.return_value = "add"
    event_tag.manage_event_tags(body, mock_client, mock_logger, mock_context, mock_region_record)
    mock_service.build_event_tag_form.assert_called_once_with(
        body, mock_client, mock_logger, mock_context, mock_region_record
    )


@patch("features.calendar.event_tag.event_tag.safe_get")
@patch("features.calendar.event_tag.event_tag.EventTagService")
def test_manage_event_tags_edit(
    mock_service, mock_safe_get, mock_client, mock_logger, mock_context, mock_region_record
):
    body = {"actions": [{"selected_option": {"value": "edit"}}]}
    mock_safe_get.return_value = "edit"
    event_tag.manage_event_tags(body, mock_client, mock_logger, mock_context, mock_region_record)
    mock_service.build_event_tag_list_form.assert_called_once_with(
        body, mock_client, mock_logger, mock_context, mock_region_record
    )


@patch("features.calendar.event_tag.event_tag.safe_get")
@patch("features.calendar.event_tag.event_tag.EventTagService")
def test_manage_event_tags_other_action(
    mock_service, mock_safe_get, mock_client, mock_logger, mock_context, mock_region_record
):
    body = {"actions": [{"selected_option": {"value": "something_else"}}]}
    mock_safe_get.return_value = "something_else"
    event_tag.manage_event_tags(body, mock_client, mock_logger, mock_context, mock_region_record)
    mock_service.build_event_tag_form.assert_not_called()
    mock_service.build_event_tag_list_form.assert_not_called()

from unittest.mock import MagicMock, patch

import pytest

from features.calendar.event_tag import event_tag_service


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_context():
    return {}


@pytest.fixture
def mock_region_record():
    mock = MagicMock()
    mock.org_id = 1
    return mock


@patch("features.calendar.event_tag.event_tag_service.EventTagDB")
@patch("features.calendar.event_tag.event_tag_service.event_tag_ui")
def test_build_event_tag_form_add(mock_ui, mock_db, mock_client, mock_logger, mock_context, mock_region_record):
    form = MagicMock()
    mock_ui.EVENT_TAG_FORM = form
    mock_db.get_all_event_tags.return_value = [MagicMock(id=1), MagicMock(id=2)]
    org_record = MagicMock()
    org_record.event_tags = []
    mock_db.get_org_record.return_value = org_record
    with (
        patch.object(event_tag_service.EventTagService, "setup_add_event_tag_form") as setup_add,
        patch.object(event_tag_service.EventTagService, "set_color_list") as set_color,
        patch.object(event_tag_service.EventTagService, "post_event_tag_form") as post_form,
    ):
        event_tag_service.EventTagService.build_event_tag_form(
            body={}, client=mock_client, logger=mock_logger, context=mock_context, region_record=mock_region_record
        )
        setup_add.assert_called()
        set_color.assert_called()
        post_form.assert_called()


@patch("features.calendar.event_tag.event_tag_service.EventTagDB")
@patch("features.calendar.event_tag.event_tag_service.event_tag_ui")
def test_build_event_tag_form_edit(mock_ui, mock_db, mock_client, mock_logger, mock_context, mock_region_record):
    form = MagicMock()
    mock_ui.EVENT_TAG_FORM = form
    mock_db.get_all_event_tags.return_value = [MagicMock(id=1), MagicMock(id=2)]
    org_record = MagicMock()
    org_record.event_tags = []
    mock_db.get_org_record.return_value = org_record
    edit_event_tag = MagicMock(id=5, name="tag", color="red")
    with (
        patch.object(event_tag_service.EventTagService, "setup_edit_event_tag_form") as setup_edit,
        patch.object(event_tag_service.EventTagService, "set_color_list") as set_color,
        patch.object(event_tag_service.EventTagService, "post_event_tag_form") as post_form,
    ):
        event_tag_service.EventTagService.build_event_tag_form(
            body={},
            client=mock_client,
            logger=mock_logger,
            context=mock_context,
            region_record=mock_region_record,
            edit_event_tag=edit_event_tag,
        )
        setup_edit.assert_called_with(form, edit_event_tag)
        set_color.assert_called()
        post_form.assert_called()


def test_filter_new_event_tags():
    all_tags = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
    existing = [MagicMock(id=2)]
    result = event_tag_service.EventTagService.filter_new_event_tags(all_tags, existing)
    assert all(tag.id != 2 for tag in result)


def test_setup_edit_event_tag_form():
    form = MagicMock()
    edit_tag = MagicMock(name="tag", color="red")
    form.blocks = [MagicMock(), MagicMock(), MagicMock()]
    event_tag_service.EventTagService.setup_edit_event_tag_form(form, edit_tag)
    form.set_initial_values.assert_called()
    assert form.blocks[0].label == "Edit Event Tag"
    assert form.blocks[0].element.placeholder == "Edit Event Tag"


def test_setup_add_event_tag_form():
    form = MagicMock()
    event_tags_new = [MagicMock(name="tag1", id=1, color="red")]
    with patch("features.calendar.event_tag.event_tag_service.orm.as_selector_options") as as_selector:
        as_selector.return_value = ["opt1"]
        event_tag_service.EventTagService.setup_add_event_tag_form(form, event_tags_new)
        form.set_options.assert_called()


def test_set_color_list():
    form = MagicMock()
    form.blocks = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    tag1 = MagicMock()
    tag1.name = "tag1"
    tag1.color = "red"
    tag2 = MagicMock()
    tag2.name = "tag2"
    tag2.color = "blue"
    event_tags = [tag1, tag2]
    event_tag_service.EventTagService.set_color_list(form, event_tags)
    assert "tag1 - red" in form.blocks[-1].label
    assert "tag2 - blue" in form.blocks[-1].label


def test_filter_new_event_tags_empty():
    all_tags = []
    existing = []
    result = event_tag_service.EventTagService.filter_new_event_tags(all_tags, existing)
    assert result == []

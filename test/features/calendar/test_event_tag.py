import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import unittest
from unittest.mock import MagicMock, patch

from f3_data_models.models import EventTag, Org

from features.calendar.event_tag import (
    CALENDAR_ADD_EVENT_TAG_COLOR,
    CALENDAR_ADD_EVENT_TAG_NEW,
    CALENDAR_EVENT_TAG_COLORS_IN_USE,
    EVENT_TAG_EDIT_DELETE,
    EventTagService,
    EventTagViews,
    handle_event_tag_add,
    handle_event_tag_edit_delete,
    manage_event_tags,
)


class EventTagServiceTest(unittest.TestCase):
    @patch("features.calendar.event_tag.DbManager")
    def test_get_org_event_tags(self, mock_db_manager):
        mock_org = Org(id="org1", name="Test Org", event_tags=[EventTag(id=1, name="Tag1", color="Red")])
        mock_db_manager.get.return_value = mock_org

        service = EventTagService()
        result = service.get_org_event_tags("org1")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Tag1")
        mock_db_manager.get.assert_called_once_with(Org, "org1", joinedloads=[Org.event_tags])

    @patch("features.calendar.event_tag.DbManager")
    def test_create_org_specific_tag(self, mock_db_manager):
        service = EventTagService()
        service.create_org_specific_tag("New Tag", "Green", "org1")

        mock_db_manager.create_record.assert_called_once()
        created_instance = mock_db_manager.create_record.call_args[0][0]
        self.assertEqual(created_instance.name, "New Tag")
        self.assertEqual(created_instance.color, "Green")
        self.assertEqual(created_instance.specific_org_id, "org1")

    @patch("features.calendar.event_tag.DbManager")
    def test_update_org_specific_tag(self, mock_db_manager):
        service = EventTagService()
        service.update_org_specific_tag(1, "Updated Tag", "Yellow")

        mock_db_manager.update_record.assert_called_once_with(
            EventTag, 1, {EventTag.name: "Updated Tag", EventTag.color: "Yellow"}
        )

    @patch("features.calendar.event_tag.DbManager")
    def test_delete_org_specific_tag(self, mock_db_manager):
        service = EventTagService()
        service.delete_org_specific_tag(1)
        mock_db_manager.delete_record.assert_called_once_with(EventTag, 1)


class EventTagViewsTest(unittest.TestCase):
    def test_build_add_tag_modal(self):
        org_tags = [EventTag(id=1, name="Tag1", color="Red")]

        views = EventTagViews()
        form = views.build_add_tag_modal(org_tags)

        self.assertEqual(len(form.blocks), 4)
        colors_block = form.get_block(CALENDAR_EVENT_TAG_COLORS_IN_USE)
        self.assertIsNotNone(colors_block)
        self.assertIn("Colors already in use:", colors_block.text.text)
        self.assertIn("Tag1 - Red", colors_block.text.text)

    def test_build_edit_tag_modal(self):
        tag_to_edit = EventTag(id=1, name="Tag1", color="Red")
        org_tags = [EventTag(id=1, name="Tag1", color="Red")]

        views = EventTagViews()
        form = views.build_edit_tag_modal(tag_to_edit, org_tags)

        self.assertEqual(len(form.blocks), 4)
        name_block = form.get_block(CALENDAR_ADD_EVENT_TAG_NEW)
        self.assertIsNotNone(name_block)
        self.assertEqual(name_block.label.text, "Edit Event Tag")
        self.assertEqual(name_block.element.initial_value, "Tag1")

    def test_build_tag_list_modal(self):
        org_tags = [EventTag(id=1, name="Tag1", color="Red")]

        views = EventTagViews()
        form = views.build_tag_list_modal(org_tags)

        self.assertEqual(len(form.blocks), 2)
        self.assertEqual(form.blocks[0].block_id, f"{EVENT_TAG_EDIT_DELETE}_1")
        self.assertEqual(form.blocks[0].accessory.action_id, f"{EVENT_TAG_EDIT_DELETE}_1")


class EventTagHandlersTest(unittest.TestCase):
    @patch("features.calendar.event_tag.add_loading_form")
    @patch("features.calendar.event_tag.EventTagViews")
    @patch("features.calendar.event_tag.EventTagService")
    def test_manage_event_tags_add(self, mock_service, mock_views, mock_add_loading_form):
        body = {"actions": [{"selected_option": {"value": "add"}}], "trigger_id": "trigger123"}
        client = MagicMock()
        logger = MagicMock()
        context = MagicMock()
        region_record = MagicMock()
        region_record.org_id = "org1"

        mock_add_loading_form.return_value = "view123"
        mock_service.return_value.get_org_event_tags.return_value = []
        mock_modal = MagicMock()
        mock_views.return_value.build_add_tag_modal.return_value = mock_modal

        manage_event_tags(body, client, logger, context, region_record)

        mock_service.return_value.get_org_event_tags.assert_called_once_with("org1")
        mock_views.return_value.build_add_tag_modal.assert_called_once_with([])
        mock_modal.update_modal.assert_called_once()

    @patch("features.calendar.event_tag.EVENT_TAG_FORM")
    @patch("features.calendar.event_tag.EventTagService")
    def test_handle_event_tag_add_new(self, mock_service, mock_form):
        mock_form.get_selected_values.return_value = {
            CALENDAR_ADD_EVENT_TAG_NEW: "New Tag",
            CALENDAR_ADD_EVENT_TAG_COLOR: "Green",
        }
        body = {"view": {"private_metadata": "{}"}}
        client = MagicMock()
        logger = MagicMock()
        context = MagicMock()
        region_record = MagicMock()
        region_record.org_id = "org1"

        handle_event_tag_add(body, client, logger, context, region_record)

        mock_service.return_value.create_org_specific_tag.assert_called_once_with("New Tag", "Green", "org1")

    @patch("features.calendar.event_tag.DbManager")
    @patch("features.calendar.event_tag.EventTagViews")
    @patch("features.calendar.event_tag.EventTagService")
    def test_handle_event_tag_edit_delete_edit(self, mock_service, mock_views, mock_db_manager):
        body = {
            "actions": [{"action_id": f"{EVENT_TAG_EDIT_DELETE}_1", "selected_option": {"value": "Edit"}}],
            "trigger_id": "trigger123",
        }
        client = MagicMock()
        logger = MagicMock()
        context = MagicMock()
        region_record = MagicMock()
        region_record.org_id = "org1"

        mock_event_tag = EventTag(id=1, name="Tag1", color="Red")
        mock_db_manager.get.return_value = mock_event_tag
        mock_modal = MagicMock()
        mock_views.return_value.build_edit_tag_modal.return_value = mock_modal

        handle_event_tag_edit_delete(body, client, logger, context, region_record)

        mock_db_manager.get.assert_called_once_with(EventTag, 1)
        mock_service.return_value.get_org_event_tags.assert_called_once_with("org1")
        mock_views.return_value.build_edit_tag_modal.assert_called_once()
        mock_modal.update_modal.assert_called_once()

    @patch("features.calendar.event_tag.EventTagService")
    def test_handle_event_tag_edit_delete_delete(self, mock_service):
        body = {"actions": [{"action_id": f"{EVENT_TAG_EDIT_DELETE}_1", "selected_option": {"value": "Delete"}}]}
        client = MagicMock()
        logger = MagicMock()
        context = MagicMock()
        region_record = MagicMock()

        handle_event_tag_edit_delete(body, client, logger, context, region_record)

        mock_service.return_value.delete_org_specific_tag.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()

from utilities.routing import ACTION_MAPPER, VIEW_MAPPER
from utilities.slack import actions

from . import event_tag, event_tag_ui
from .event_tag_service import EventTagService

VIEW_MAPPER.update(
    {
        event_tag_ui.CALENDAR_ADD_EVENT_TAG_CALLBACK_ID: (EventTagService.handle_event_tag_add, False),
    }
)

ACTION_MAPPER.update(
    {
        actions.CALENDAR_MANAGE_EVENT_TAGS: (event_tag.manage_event_tags, False),
        event_tag_ui.EVENT_TAG_EDIT_DELETE: (EventTagService.handle_event_tag_edit_delete, False),
    }
)

actions.ACTION_PREFIXES.append(event_tag_ui.EVENT_TAG_EDIT_DELETE)

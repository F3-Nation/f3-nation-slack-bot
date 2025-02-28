from utilities.constants import EVENT_TAG_COLORS
from utilities.slack import orm

CALENDAR_ADD_EVENT_TAG_SELECT = "calendar_add_event_tag_select"
CALENDAR_ADD_EVENT_TAG_NEW = "calendar_add_event_tag_new"
CALENDAR_ADD_EVENT_TAG_COLOR = "calendar_add_event_tag_color"
CALENDAR_ADD_EVENT_TAG_CALLBACK_ID = "calendar_add_event_tag"
EVENT_TAG_EDIT_DELETE = "event_tag_edit_delete"
EDIT_DELETE_AO_CALLBACK_ID = "edit_delete_ao"

EVENT_TAG_FORM = orm.BlockView(
    blocks=[
        orm.InputBlock(
            label="Select from commonly used event tags",
            element=orm.StaticSelectElement(placeholder="Select from commonly used event tags"),
            optional=True,
            action=CALENDAR_ADD_EVENT_TAG_SELECT,
        ),
        orm.DividerBlock(),
        orm.InputBlock(
            label="Or create a new event tag",
            element=orm.PlainTextInputElement(placeholder="New event tag"),
            action=CALENDAR_ADD_EVENT_TAG_NEW,
            optional=True,
        ),
        orm.InputBlock(
            label="Event tag color",
            element=orm.StaticSelectElement(
                placeholder="Select a color",
                options=orm.as_selector_options(names=list(EVENT_TAG_COLORS.keys())),
            ),
            action=CALENDAR_ADD_EVENT_TAG_COLOR,
            optional=True,
            hint="This is the color that will be shown on the calendar",
        ),
        orm.SectionBlock(label="Colors already in use:"),
    ]
)

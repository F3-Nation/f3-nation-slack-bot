from typing import List

from utilities.slack import actions, orm

PREBLAST_MESSAGE_ACTION_ELEMENTS = [
    orm.ButtonElement(label=":hc: HC/Un-HC", action=actions.EVENT_PREBLAST_HC_UN_HC),
    orm.ButtonElement(label=":pencil: Edit Preblast", action=actions.EVENT_PREBLAST_EDIT, value="Edit Preblast"),
]


def get_preblast_action_buttons(has_q: bool = True, event_instance_id: int = None) -> List[orm.ButtonElement]:
    buttons = [
        orm.ButtonElement(label=":hc: HC/Un-HC", action=actions.EVENT_PREBLAST_HC_UN_HC),
        orm.ButtonElement(label=":pencil: Edit Preblast", action=actions.EVENT_PREBLAST_EDIT, value="Edit Preblast"),
        orm.ButtonElement(label=":heavy_plus_sign: New Preblast", action=actions.NEW_PREBLAST_BUTTON),
    ]
    if not has_q:
        buttons.append(
            orm.ButtonElement(
                label=":raising_hand: Take Q", action=actions.EVENT_PREBLAST_TAKE_Q, value=str(event_instance_id)
            )
        )
    if event_instance_id:
        buttons.append(
            orm.ButtonElement(
                label=":back: Fill Backblast",
                action=actions.FILL_BACKBLAST_BUTTON,
                value=str(event_instance_id),
            )
        )
    return buttons

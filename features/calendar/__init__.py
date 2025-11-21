from utilities.slack import actions, orm

PREBLAST_MESSAGE_ACTION_ELEMENTS = [
    orm.ButtonElement(label=":hc: HC/Un-HC", action=actions.EVENT_PREBLAST_HC_UN_HC),
    orm.ButtonElement(label=":pencil: Edit Preblast", action=actions.EVENT_PREBLAST_EDIT, value="Edit Preblast"),
]

PREBLAST_MESSAGE_ACTION_ELEMENTS_NO_Q = PREBLAST_MESSAGE_ACTION_ELEMENTS.insert(
    0, orm.ButtonElement(label=":man_raising_hand: Take Q", action=actions.EVENT_PREBLAST_TAKE_Q)
)

import json
from typing import Any, Dict, List

from slack_sdk.models.blocks import Block, ImageBlock, InputBlock, SectionBlock
from slack_sdk.models.views import View

from utilities.helper_functions import safe_get


class SdkBlockView:
    """
    A wrapper for building Slack views using slack_sdk.models objects.
    This provides similar functionality to the custom BlockView but uses the
    official slack_sdk components as the base.
    """

    def __init__(self, blocks: List[Block]):
        self.blocks = blocks

    def delete_block(self, block_id: str):
        """Removes a block from the view by its block_id."""
        self.blocks = [b for b in self.blocks if getattr(b, "block_id", None) != block_id]

    def add_block(self, block: Block):
        """Adds a block to the view."""
        self.blocks.append(block)

    def set_initial_values(self, values: dict):
        """
        Sets initial values for elements within the blocks.
        NOTE: This has limited support and works best with InputBlocks.
        """
        for block in self.blocks:
            if isinstance(block, InputBlock) and block.block_id in values:
                if hasattr(block.element, "initial_value"):
                    block.element.initial_value = values[block.block_id]
                elif hasattr(block.element, "initial_options"):
                    # This requires creating Option objects, which is more complex.
                    # For now, this part is not fully supported for multi-selects.
                    pass
                elif hasattr(block.element, "initial_option"):
                    # This requires creating an Option object, which is more complex.
                    # For now, this part is not fully supported for single selects.
                    pass
            elif isinstance(block, SectionBlock) and block.block_id in values:
                if hasattr(block.text, "text"):
                    block.text.text = values[block.block_id]
            elif isinstance(block, ImageBlock) and block.block_id in values:
                block.image_url = values[block.block_id]

    def set_options(self, options: Dict[str, List]):
        """
        Sets options for select elements within the blocks.
        NOTE: The options should be a list of slack_sdk.models.composition_objects.Option objects.
        """
        for block in self.blocks:
            if isinstance(block, InputBlock) and block.block_id in options:
                if hasattr(block.element, "options"):
                    block.element.options = options[block.block_id]

    def to_dict_list(self) -> List[dict]:
        """Serializes all blocks to a list of dictionaries."""
        return [b.to_dict() for b in self.blocks]

    def get_selected_values(self, body: dict) -> dict:
        """
        Parses the selected values from a view_submission payload.
        This is based on the structure of `view.state.values`.
        """
        values = safe_get(body, "view", "state", "values")
        if not values:
            return {}

        selected_values = {}
        for block_id, block_values in values.items():
            for _, state in block_values.items():
                element_type = state.get("type")
                value = None
                if element_type in [
                    "plain_text_input",
                    "email_text_input",
                    "url_text_input",
                    "number_input",
                    "datepicker",
                    "timepicker",
                ]:
                    value = state.get("value")
                elif element_type in ["users_select", "conversations_select", "channels_select"]:
                    value = (
                        state.get("selected_user")
                        or state.get("selected_conversation")
                        or state.get("selected_channel")
                    )
                elif element_type in ["multi_users_select", "multi_conversations_select", "multi_channels_select"]:
                    value = (
                        state.get("selected_users")
                        or state.get("selected_conversations")
                        or state.get("selected_channels")
                    )
                elif element_type in ["static_select", "external_select", "radio_buttons"]:
                    if state.get("selected_option"):
                        value = state.get("selected_option", {}).get("value")
                elif element_type in ["multi_static_select", "multi_external_select", "checkboxes"]:
                    value = [o.get("value") for o in state.get("selected_options", [])]
                elif element_type == "rich_text_input":
                    value = state.get("rich_text_value")
                elif element_type == "file_input":
                    value = state.get("files")

                selected_values[block_id] = value
        return selected_values

    def post_modal(
        self,
        client: Any,
        trigger_id: str,
        title_text: str,
        callback_id: str,
        submit_button_text: str = "Submit",
        parent_metadata: dict = None,
        close_button_text: str = "Close",
        notify_on_close: bool = False,
        new_or_add: str = "new",
    ) -> dict:
        """Posts the view as a new modal."""
        view = View(
            type="modal",
            callback_id=callback_id,
            title=title_text,
            close=close_button_text,
            notify_on_close=notify_on_close,
            blocks=self.blocks,
            submit=submit_button_text if submit_button_text and submit_button_text.lower() != "none" else None,
        )
        if parent_metadata:
            view.private_metadata = json.dumps(parent_metadata)

        if new_or_add == "new":
            return client.views_open(trigger_id=trigger_id, view=view.to_dict())
        elif new_or_add == "add":
            return client.views_push(trigger_id=trigger_id, view=view.to_dict())

    def update_modal(
        self,
        client: Any,
        view_id: str,
        title_text: str,
        callback_id: str,
        submit_button_text: str = "Submit",
        parent_metadata: dict = None,
        close_button_text: str = "Close",
        notify_on_close: bool = False,
    ):
        """Updates an existing modal view."""
        view = View(
            type="modal",
            callback_id=callback_id,
            title=title_text,
            close=close_button_text,
            notify_on_close=notify_on_close,
            blocks=self.blocks,
            submit=submit_button_text if submit_button_text and submit_button_text.lower() != "none" else None,
        )
        if parent_metadata:
            view.private_metadata = json.dumps(parent_metadata)

        return client.views_update(view_id=view_id, view=view.to_dict())

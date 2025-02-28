from typing import List

from f3_data_models.models import EventTag, Org
from f3_data_models.utils import DbManager


class EventTagDB:
    @staticmethod
    def get_all_event_tags() -> List[EventTag]:
        return DbManager.find_records(EventTag, [True])

    @staticmethod
    def get_org_record(org_id: int) -> Org:
        return DbManager.get(Org, org_id, joinedloads="all")

    @staticmethod
    def get_event_tag(event_tag_id: int) -> EventTag:
        return DbManager.get(EventTag, event_tag_id)

    @staticmethod
    def create_event_tag(event_tag: EventTag):
        DbManager.create_record(event_tag)

    @staticmethod
    def update_event_tag(event_tag_id: int, event_tag_color: str, event_color: str):
        DbManager.update_record(
            EventTag,
            event_tag_id,
            {EventTag.color: event_color, EventTag.name: event_tag_color},
        )

    @staticmethod
    def delete_event_tag(event_tag_id: int):
        DbManager.delete_record(EventTag, event_tag_id)

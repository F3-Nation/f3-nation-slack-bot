from __future__ import annotations

from typing import List

from application.dto import (
    EventTagDTO,
    EventTypeDTO,
    LocationDTO,
    PositionDTO,
    to_event_tag_dto,
    to_event_type_dto,
    to_location_dto,
    to_position_dto,
)
from domain.org.repository import OrgRepository
from domain.org.value_objects import OrgId


class OrgQueryService:
    def __init__(self, repo: OrgRepository):
        self.repo = repo

    # Separate getters
    def get_locations(self, org_id: int, *, only_active: bool = True) -> List[LocationDTO]:
        locs = self.repo.get_locations(OrgId(int(org_id)), only_active=only_active)
        return [to_location_dto(loc) for loc in locs]

    def get_event_types(
        self, org_id: int, *, include_global: bool = True, only_active: bool = True
    ) -> List[EventTypeDTO]:
        ets = self.repo.get_event_types(OrgId(int(org_id)), include_global=include_global, only_active=only_active)
        # We can’t easily tell which came from global here without changing repo contract; mark as region.
        return [to_event_type_dto(e, scope="region") for e in ets]

    def get_event_tags(
        self, org_id: int, *, include_global: bool = True, only_active: bool = True
    ) -> List[EventTagDTO]:
        tags = self.repo.get_event_tags(OrgId(int(org_id)), include_global=include_global, only_active=only_active)
        return [to_event_tag_dto(t, scope="region") for t in tags]

    def get_positions(self, org_id: int, *, include_global: bool = True) -> List[PositionDTO]:
        pos = self.repo.get_positions(OrgId(int(org_id)), include_global=include_global)
        return [to_position_dto(p, scope="region") for p in pos]

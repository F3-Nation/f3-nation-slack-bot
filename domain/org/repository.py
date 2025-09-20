from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from .entities import EventType, Location, Org
from .value_objects import OrgId


class OrgRepository(ABC):
    """Port interface for Org aggregate persistence."""

    @abstractmethod
    def get(self, org_id: OrgId) -> Optional[Org]: ...

    @abstractmethod
    def save(self, org: Org) -> None: ...

    @abstractmethod
    def list_children(self, parent_id: OrgId, include_inactive: bool = False) -> List[Org]: ...

    # Query helpers
    @abstractmethod
    def get_locations_and_event_types(
        self,
        org_id: OrgId,
        *,
        include_global_event_types: bool = True,
        only_active: bool = True,
    ) -> Tuple[List[Location], List[EventType]]: ...

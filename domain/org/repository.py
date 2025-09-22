from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .entities import EventTag, EventType, Location, Org, Position
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
    def get_locations(self, org_id: OrgId, *, only_active: bool = True) -> List[Location]: ...

    @abstractmethod
    def get_event_types(
        self, org_id: OrgId, *, include_global: bool = True, only_active: bool = True
    ) -> List[EventType]: ...

    @abstractmethod
    def get_event_tags(
        self, org_id: OrgId, *, include_global: bool = True, only_active: bool = True
    ) -> List[EventTag]: ...

    @abstractmethod
    def get_positions(self, org_id: OrgId, *, include_global: bool = True) -> List[Position]: ...

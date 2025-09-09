from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entities import Org
from .value_objects import OrgId


class OrgRepository(ABC):
    """Port interface for Org aggregate persistence."""

    @abstractmethod
    def get(self, org_id: OrgId) -> Optional[Org]: ...

    @abstractmethod
    def save(self, org: Org) -> None: ...

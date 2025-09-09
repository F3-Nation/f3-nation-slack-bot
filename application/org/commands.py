from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.org.value_objects import OrgId


@dataclass
class UpdateRegionProfile:
    org_id: OrgId
    name: Optional[str] = None
    description: Optional[str] = None

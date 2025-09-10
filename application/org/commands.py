from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.org.value_objects import OrgId


@dataclass
class UpdateRegionProfile:
    org_id: OrgId
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    logo_url: Optional[str] = None
    admin_user_ids: Optional[list[int]] = None

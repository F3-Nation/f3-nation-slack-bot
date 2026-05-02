from dataclasses import dataclass


@dataclass
class EventTagData:
    id: int
    name: str
    color: str | None
    specific_org_id: int | None
    is_active: bool = True
    description: str | None = None

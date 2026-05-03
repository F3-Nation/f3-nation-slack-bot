from application.event_tag import EventTagData
from application.event_tag.repository import EventTagRepository
from infrastructure.api_client import get_api_event_tag_repository


class EventTagService:
    """
    Business logic for event tags.  All data access is delegated to an
    ``EventTagRepository``; the default implementation uses the F3 Nation API.
    """

    def __init__(self, repository: EventTagRepository | None = None) -> None:
        self._repository: EventTagRepository = repository or get_api_event_tag_repository()

    def get_org_event_tags(self, org_id: str) -> list[EventTagData]:
        """Return org-specific event tags for *org_id*."""
        return self._repository.get_by_org(int(org_id))

    def get_event_tag_by_id(self, tag_id: int) -> EventTagData | None:
        """Return a single event tag, or *None* if not found."""
        return self._repository.get_by_id(tag_id)

    def create_org_specific_tag(self, name: str, color: str, org_id: str) -> None:
        """Create a new org-specific event tag."""
        self._repository.create(name, color, int(org_id))

    def update_org_specific_tag(self, tag_id: int, name: str, color: str) -> None:
        """Update the name and colour of an existing event tag."""
        self._repository.update(tag_id, name, color)

    def delete_org_specific_tag(self, tag_id: int) -> None:
        """Soft-delete an event tag."""
        self._repository.delete(tag_id)

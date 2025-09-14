from __future__ import annotations

from typing import List, Optional

from domain.org.value_objects import OrgId

from .entities import EventInstance, EventSeries
from .value_objects import EventInstanceId, EventSeriesId


class EventSeriesRepository:
    def get(self, series_id: EventSeriesId) -> Optional[EventSeries]:  # pragma: no cover - interface
        raise NotImplementedError

    def save(self, series: EventSeries) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def list_for_org(self, org_id: OrgId, include_inactive: bool = False) -> List[EventSeries]:  # pragma: no cover
        raise NotImplementedError


class EventInstanceRepository:
    def get(self, instance_id: EventInstanceId) -> Optional[EventInstance]:  # pragma: no cover - interface
        raise NotImplementedError

    def save(self, instance: EventInstance) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def list_for_org(
        self, org_id: OrgId, include_inactive: bool = False
    ) -> List[EventInstance]:  # pragma: no cover - interface
        raise NotImplementedError

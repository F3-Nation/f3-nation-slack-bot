from __future__ import annotations

from typing import List, Optional

from f3_data_models.models import Event as SAEvent  # series table
from f3_data_models.models import EventInstance as SAEventInstance
from f3_data_models.utils import DbManager

from domain.event.entities import EventInstance, EventSeries
from domain.event.repository import EventInstanceRepository, EventSeriesRepository
from domain.event.value_objects import EventInstanceId, EventName, EventSeriesId, TimeHHMM
from domain.org.value_objects import OrgId


class SqlAlchemyEventSeriesRepository(EventSeriesRepository):
    def get(self, series_id: EventSeriesId) -> Optional[EventSeries]:
        rec: SAEvent = DbManager.get(SAEvent, int(series_id))
        if not rec:
            return None
        s = EventSeries(
            id=EventSeriesId(rec.id),
            org_id=OrgId(rec.org_id),
            name=EventName(rec.name),
            description=rec.description,
            location_id=rec.location_id,
            start_date=rec.start_date,
            end_date=rec.end_date,
            start_time=TimeHHMM(rec.start_time) if rec.start_time else None,
            end_time=TimeHHMM(rec.end_time) if rec.end_time else None,
            day_of_week=rec.day_of_week,
            recurrence_pattern=getattr(rec, "recurrence_pattern", None),
            recurrence_interval=getattr(rec, "recurrence_interval", None),
            index_within_interval=getattr(rec, "index_within_interval", None),
            is_active=rec.is_active,
        )
        return s

    def save(self, series: EventSeries) -> None:
        payload = {
            SAEvent.name: series.name.value,
            SAEvent.description: series.description,
            SAEvent.location_id: series.location_id,
            SAEvent.start_date: series.start_date,
            SAEvent.end_date: series.end_date,
            SAEvent.start_time: series.start_time.value if series.start_time else None,
            SAEvent.end_time: series.end_time.value if series.end_time else None,
            SAEvent.day_of_week: series.day_of_week,
            SAEvent.recurrence_pattern: series.recurrence_pattern,
            SAEvent.recurrence_interval: series.recurrence_interval,
            SAEvent.index_within_interval: series.index_within_interval,
            SAEvent.is_active: series.is_active,
        }
        if series.id:
            DbManager.update_record(SAEvent, int(series.id), payload)
        else:  # create
            rec = DbManager.create_record(SAEvent(org_id=int(series.org_id), **{k.key: v for k, v in payload.items()}))
            series.id = EventSeriesId(rec.id)

    def list_for_org(self, org_id: OrgId, include_inactive: bool = False) -> List[EventSeries]:
        filters = [SAEvent.org_id == int(org_id)]
        if not include_inactive:
            filters.append(SAEvent.is_active.is_(True))
        rows = DbManager.find_records(SAEvent, filters)
        return [self.get(EventSeriesId(r.id)) for r in rows]


class SqlAlchemyEventInstanceRepository(EventInstanceRepository):
    def get(self, instance_id: EventInstanceId) -> Optional[EventInstance]:
        rec: SAEventInstance = DbManager.get(SAEventInstance, int(instance_id))
        if not rec:
            return None
        i = EventInstance(
            id=EventInstanceId(rec.id),
            org_id=OrgId(rec.org_id),
            name=EventName(rec.name),
            date=rec.start_date,
            description=rec.description,
            location_id=rec.location_id,
            series_id=EventSeriesId(rec.series_id) if rec.series_id else None,
            start_time=TimeHHMM(rec.start_time) if rec.start_time else None,
            end_time=TimeHHMM(rec.end_time) if rec.end_time else None,
            is_active=rec.is_active,
        )
        return i

    def save(self, instance: EventInstance) -> None:
        payload = {
            SAEventInstance.name: instance.name.value,
            SAEventInstance.description: instance.description,
            SAEventInstance.location_id: instance.location_id,
            SAEventInstance.start_date: instance.date,
            SAEventInstance.start_time: instance.start_time.value if instance.start_time else None,
            SAEventInstance.end_time: instance.end_time.value if instance.end_time else None,
            SAEventInstance.series_id: int(instance.series_id) if instance.series_id else None,
            SAEventInstance.is_active: instance.is_active,
        }
        if instance.id:
            DbManager.update_record(SAEventInstance, int(instance.id), payload)
        else:
            rec = DbManager.create_record(
                SAEventInstance(org_id=int(instance.org_id), **{k.key: v for k, v in payload.items()})
            )
            instance.id = EventInstanceId(rec.id)

    def list_for_org(self, org_id: OrgId, include_inactive: bool = False) -> List[EventInstance]:
        filters = [SAEventInstance.org_id == int(org_id)]
        if not include_inactive:
            filters.append(SAEventInstance.is_active.is_(True))
        rows = DbManager.find_records(SAEventInstance, filters)
        return [self.get(EventInstanceId(r.id)) for r in rows]

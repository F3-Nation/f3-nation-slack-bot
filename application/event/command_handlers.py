from __future__ import annotations

from domain.event.entities import EventInstance, EventSeries
from domain.event.repository import EventInstanceRepository, EventSeriesRepository
from domain.org.value_objects import OrgId, UserId

from .commands import (
    CreateInstance,
    CreateSeries,
    DeactivateInstance,
    DeactivateSeries,
    UpdateInstance,
    UpdateSeries,
)


class EventCommandHandler:
    def __init__(self, series_repo: EventSeriesRepository, instance_repo: EventInstanceRepository):
        self.series_repo = series_repo
        self.instance_repo = instance_repo

    def handle(self, command):
        if isinstance(command, CreateSeries):
            return self._handle_create_series(command)
        if isinstance(command, UpdateSeries):
            return self._handle_update_series(command)
        if isinstance(command, DeactivateSeries):
            return self._handle_deactivate_series(command)
        if isinstance(command, CreateInstance):
            return self._handle_create_instance(command)
        if isinstance(command, UpdateInstance):
            return self._handle_update_instance(command)
        if isinstance(command, DeactivateInstance):
            return self._handle_deactivate_instance(command)
        raise ValueError(f"Unhandled command type: {type(command)}")

    def _handle_create_series(self, cmd: CreateSeries):
        s = EventSeries.create(
            OrgId(cmd.org_id),
            cmd.name,
            triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None,
            description=cmd.description,
            location_id=cmd.location_id,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            day_of_week=cmd.day_of_week,
            recurrence_pattern=cmd.recurrence_pattern,
            recurrence_interval=cmd.recurrence_interval,
            index_within_interval=cmd.index_within_interval,
        )
        self.series_repo.save(s)
        return s

    def _handle_update_series(self, cmd: UpdateSeries):
        s = self.series_repo.get(cmd.series_id)
        if not s:
            raise ValueError("Series not found")
        s.update_profile(
            name=cmd.name,
            description=cmd.description,
            location_id=cmd.location_id,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            day_of_week=cmd.day_of_week,
            recurrence_pattern=cmd.recurrence_pattern,
            recurrence_interval=cmd.recurrence_interval,
            index_within_interval=cmd.index_within_interval,
            triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None,
        )
        self.series_repo.save(s)
        return s

    def _handle_deactivate_series(self, cmd: DeactivateSeries):
        s = self.series_repo.get(cmd.series_id)
        if not s:
            raise ValueError("Series not found")
        s.deactivate(triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None)
        self.series_repo.save(s)
        return True

    def _handle_create_instance(self, cmd: CreateInstance):
        inst = EventInstance.create(
            OrgId(cmd.org_id),
            cmd.name,
            cmd.date,
            series_id=cmd.series_id,
            triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None,
            description=cmd.description,
            location_id=cmd.location_id,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
        )
        self.instance_repo.save(inst)
        return inst

    def _handle_update_instance(self, cmd: UpdateInstance):
        inst = self.instance_repo.get(cmd.instance_id)
        if not inst:
            raise ValueError("Instance not found")
        inst.update_profile(
            name=cmd.name,
            date=cmd.date,
            description=cmd.description,
            location_id=cmd.location_id,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None,
        )
        self.instance_repo.save(inst)
        return inst

    def _handle_deactivate_instance(self, cmd: DeactivateInstance):
        inst = self.instance_repo.get(cmd.instance_id)
        if not inst:
            raise ValueError("Instance not found")
        inst.deactivate(triggered_by=UserId(cmd.triggered_by) if cmd.triggered_by else None)
        self.instance_repo.save(inst)
        return True

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


# Series commands
@dataclass
class CreateSeries:
    org_id: int
    name: str
    description: Optional[str] = None
    location_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None  # HHMM
    end_time: Optional[str] = None  # HHMM
    day_of_week: Optional[int] = None
    recurrence_pattern: Optional[str] = None
    recurrence_interval: Optional[int] = None
    index_within_interval: Optional[int] = None
    triggered_by: Optional[int] = None


@dataclass
class UpdateSeries:
    series_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    day_of_week: Optional[int] = None
    recurrence_pattern: Optional[str] = None
    recurrence_interval: Optional[int] = None
    index_within_interval: Optional[int] = None
    triggered_by: Optional[int] = None


@dataclass
class DeactivateSeries:
    series_id: int
    triggered_by: Optional[int] = None


# Instance commands
@dataclass
class CreateInstance:
    org_id: int
    name: str
    date: date
    description: Optional[str] = None
    location_id: Optional[int] = None
    series_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class UpdateInstance:
    instance_id: int
    name: Optional[str] = None
    date: Optional[date] = None
    description: Optional[str] = None
    location_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    triggered_by: Optional[int] = None


@dataclass
class DeactivateInstance:
    instance_id: int
    triggered_by: Optional[int] = None

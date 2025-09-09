from __future__ import annotations

from typing import Optional

from f3_data_models.models import EventType as SAEventType  # type: ignore
from f3_data_models.models import Org as SAOrg  # type: ignore
from f3_data_models.utils import DbManager

from domain.org.entities import EventType, Org
from domain.org.repository import OrgRepository
from domain.org.value_objects import Acronym, EventTypeId, EventTypeName, OrgId

"""SQLAlchemy implementation of OrgRepository.

This is a placeholder that adapts the existing DbManager / f3_data_models models.
Later we can optimize queries and handle version checking.
"""


class SqlAlchemyOrgRepository(OrgRepository):
    def get(self, org_id: OrgId) -> Optional[Org]:
        sa_org: SAOrg = DbManager.get(SAOrg, org_id)
        if not sa_org:
            return None
        # build aggregate (minimal fields for now)
        org = Org(
            id=OrgId(sa_org.id),
            parent_id=OrgId(sa_org.parent_id) if sa_org.parent_id else None,
            type=sa_org.org_type.name if getattr(sa_org, "org_type", None) else "region",
            name=sa_org.name,
            description=sa_org.description,
            version=getattr(sa_org, "version", 0) or 0,
        )
        # load custom event types for this org
        event_type_records = DbManager.find_records(
            SAEventType,
            [SAEventType.specific_org_id == sa_org.id, SAEventType.is_active],
        )
        for rec in event_type_records:
            et = EventType(
                id=EventTypeId(rec.id),
                name=EventTypeName(rec.name),
                acronym=Acronym(rec.acronym or rec.name[:2]),
                category=getattr(rec, "event_category", "first_f"),
                is_active=rec.is_active,
            )
            org.event_types[et.id] = et
        org.rebuild_indexes()
        return org

    def save(self, org: Org) -> None:
        # persist simple scalar changes for org
        DbManager.update_record(SAOrg, org.id, {SAOrg.name: org.name, SAOrg.description: org.description})
        # event type changes (only handle additions + soft deletes for now)
        # existing set from DB
        existing = {rec.id for rec in DbManager.find_records(SAEventType, [SAEventType.specific_org_id == org.id])}
        for et in org.event_types.values():
            if et.id not in existing:
                DbManager.create_record(
                    SAEventType(
                        name=et.name.value,
                        event_category=et.category,
                        acronym=et.acronym.value,
                        specific_org_id=org.id,
                        is_active=et.is_active,
                    )
                )
            else:
                # update active flag / fields
                DbManager.update_record(
                    SAEventType,
                    et.id,
                    {
                        SAEventType.name: et.name.value,
                        SAEventType.acronym: et.acronym.value,
                        SAEventType.event_category: et.category,
                        SAEventType.is_active: et.is_active,
                    },
                )
        # NOTE: not handling deletions explicitly (soft delete only)

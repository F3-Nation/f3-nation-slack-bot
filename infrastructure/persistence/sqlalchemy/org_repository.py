from __future__ import annotations

from typing import Optional

from f3_data_models.models import EventTag as SAEventTag  # type: ignore
from f3_data_models.models import EventType as SAEventType  # type: ignore
from f3_data_models.models import Org as SAOrg  # type: ignore
from f3_data_models.utils import DbManager

from domain.org.entities import EventTag, EventType, Org
from domain.org.repository import OrgRepository
from domain.org.value_objects import Acronym, EventTagId, EventTagName, EventTypeId, EventTypeName, OrgId

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
            website=getattr(sa_org, "website", None),
            email=getattr(sa_org, "email", None),
            twitter=getattr(sa_org, "twitter", None),
            facebook=getattr(sa_org, "facebook", None),
            instagram=getattr(sa_org, "instagram", None),
            logo_url=getattr(sa_org, "logo_url", None),
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
        # load custom event tags for this org
        # include both active and inactive to preserve soft-deleted items in aggregate
        event_tag_records = DbManager.find_records(
            SAEventTag,
            [SAEventTag.specific_org_id == sa_org.id],
        )
        for rec in event_tag_records:
            tag = EventTag(
                id=EventTagId(rec.id),
                name=EventTagName(rec.name),
                color=rec.color,
                is_active=rec.is_active,
            )
            org.event_tags[tag.id] = tag
        org.rebuild_indexes()
        return org

    def save(self, org: Org) -> None:
        # persist simple scalar changes for org
        base_fields = {SAOrg.name: org.name, SAOrg.description: org.description}
        for attr in ["website", "email", "twitter", "facebook", "instagram", "logo_url"]:
            if hasattr(SAOrg, attr):
                base_fields[getattr(SAOrg, attr)] = getattr(org, attr)
        DbManager.update_record(SAOrg, org.id, base_fields)
        # event type changes
        existing_types = {
            rec.id: rec for rec in DbManager.find_records(SAEventType, [SAEventType.specific_org_id == org.id])
        }
        for et in list(org.event_types.values()):
            if et.id not in existing_types:
                sa_obj = DbManager.create_record(
                    SAEventType(
                        name=et.name.value,
                        event_category=et.category,
                        acronym=et.acronym.value,
                        specific_org_id=org.id,
                        is_active=et.is_active,
                    )
                )
                # remap domain id to persistence id if different
                if sa_obj.id != et.id:
                    old_id = et.id
                    et.id = EventTypeId(sa_obj.id)
                    org.event_types[et.id] = et
                    org.event_types.pop(old_id, None)
            else:
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

        # event tag changes
        existing_tags = {
            rec.id: rec for rec in DbManager.find_records(SAEventTag, [SAEventTag.specific_org_id == org.id])
        }
        for tag in list(org.event_tags.values()):
            if tag.id not in existing_tags:
                sa_obj = DbManager.create_record(
                    SAEventTag(
                        name=tag.name.value,
                        color=tag.color,
                        specific_org_id=org.id,
                        is_active=tag.is_active,
                    )
                )
                if sa_obj.id != tag.id:
                    old_id = tag.id
                    tag.id = EventTagId(sa_obj.id)
                    org.event_tags[tag.id] = tag
                    org.event_tags.pop(old_id, None)
            else:
                DbManager.update_record(
                    SAEventTag,
                    tag.id,
                    {
                        SAEventTag.name: tag.name.value,
                        SAEventTag.color: tag.color,
                        SAEventTag.is_active: tag.is_active,
                    },
                )

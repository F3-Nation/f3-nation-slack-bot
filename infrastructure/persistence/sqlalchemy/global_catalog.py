from __future__ import annotations

import os
import time
from typing import Dict, Optional, Protocol, Set, Tuple

from f3_data_models.models import EventTag as SAEventTag  # type: ignore
from f3_data_models.models import EventType as SAEventType  # type: ignore
from f3_data_models.models import Position as SAPosition  # type: ignore
from f3_data_models.utils import DbManager

from domain.org.entities import Position
from domain.org.value_objects import PositionId, PositionName


class GlobalCatalogProvider(Protocol):
    """Provider interface for retrieving the global catalog used by org aggregates.

    Returns a 5-tuple:
    - set of global event type names (lower-cased)
    - set of global event type acronyms (upper-cased)
    - set of global event tag names (lower-cased)
    - map of org_type -> set of position names (lower-cased)
    - map of global position id (int) -> Position domain object
    """

    def get_global_catalog(
        self,
    ) -> Tuple[Set[str], Set[str], Set[str], Dict[Optional[str], Set[str]], Dict[int, Position]]: ...


class InMemorySqlAlchemyGlobalCatalog(GlobalCatalogProvider):
    """In-process TTL cache backed by the SQLAlchemy models via DbManager.

    This keeps behavior identical to the previous class-level cache, while
    allowing an alternative provider (e.g., Redis-backed) to be swapped in.
    """

    def __init__(self, ttl_sec: Optional[int] = None) -> None:
        self._ttl = int(ttl_sec if ttl_sec is not None else os.environ.get("ORG_GLOBAL_CATALOG_TTL", "300"))
        self._cache: dict = {
            "expires": 0.0,
            "type_names": set(),
            "type_acros": set(),
            "tag_names": set(),
            "position_names_by_type": {},
            "global_positions": {},
        }

    def get_global_catalog(
        self,
    ) -> Tuple[Set[str], Set[str], Set[str], Dict[Optional[str], Set[str]], Dict[int, Position]]:
        now = time.time()
        # Fast path: return cached 5‑tuple (includes global position domain objects)
        if self._ttl > 0 and now < float(self._cache.get("expires", 0)):
            return (
                set(self._cache.get("type_names", set())),
                set(self._cache.get("type_acros", set())),
                set(self._cache.get("tag_names", set())),
                dict(self._cache.get("position_names_by_type", {})),
                dict(self._cache.get("global_positions", {})),
            )

        # Fetch active global (specific_org_id is NULL) types/tags
        type_filters = [SAEventType.specific_org_id.is_(None)]
        if hasattr(SAEventType, "is_active"):
            type_filters.append(SAEventType.is_active.is_(True))  # type: ignore[attr-defined]
        tag_filters = [SAEventTag.specific_org_id.is_(None)]
        if hasattr(SAEventTag, "is_active"):
            tag_filters.append(SAEventTag.is_active.is_(True))  # type: ignore[attr-defined]
        global_types = DbManager.find_records(SAEventType, type_filters)
        global_tags = DbManager.find_records(SAEventTag, tag_filters)

        # Global positions are those with org_id is NULL
        pos_filters = [SAPosition.org_id.is_(None)]
        global_position_rows = DbManager.find_records(SAPosition, pos_filters)

        type_names = {str(getattr(t, "name", "")).strip().lower() for t in global_types if getattr(t, "name", None)}
        type_acros = {
            (str(getattr(t, "acronym", None)) or str(getattr(t, "name", ""))[:2]).strip().upper() for t in global_types
        }
        tag_names = {str(getattr(t, "name", "")).strip().lower() for t in global_tags if getattr(t, "name", None)}

        # Build map of org_type -> set of names (normalized lower) and global positions
        pos_map: Dict[Optional[str], Set[str]] = {}
        global_position_map: Dict[int, Position] = {}
        for p in global_position_rows:
            key: Optional[str] = None
            ot = getattr(p, "org_type", None)
            if ot is not None:
                try:
                    key = str(ot.name).strip().lower()
                except Exception:
                    key = str(ot).strip().lower()
            bucket = pos_map.setdefault(key, set())
            raw_name = str(getattr(p, "name", "")).strip()
            nm = raw_name.lower()
            if nm:
                bucket.add(nm)
            # Build domain Position (treat all global as active)
            global_position_map[p.id] = Position(
                id=PositionId(p.id),
                name=PositionName(raw_name),
                org_type=key,
                description=getattr(p, "description", None),
                is_active=True,
            )

        self._cache = {
            "expires": now + (self._ttl if self._ttl > 0 else 0),
            "type_names": type_names,
            "type_acros": type_acros,
            "tag_names": tag_names,
            "position_names_by_type": pos_map,
            "global_positions": global_position_map,
        }
        return set(type_names), set(type_acros), set(tag_names), pos_map, global_position_map

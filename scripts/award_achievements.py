"""Daily (idempotent) auto-award achievements script.

Usage (from repo root, with env + poetry activated):
  poetry run python scripts/award_achievements.py --dry-run

Core logic:
  1. Load active, auto_award achievements
  2. For each achievement + each relevant (award_year, award_period) within the current year
     (or lifetime), compute the metric defined by auto_threshold_type subject to auto_filters
  3. Identify users whose metric >= auto_threshold
  4. Respect region scoping (specific_org_id => user.home_region_id must match)
  5. Insert missing rows into achievements_x_users (award_year/period keyed) (unless --dry-run)

Idempotent: already-awarded combinations are skipped.

Assumptions / notes:
  - award_year == calendar year (UTC) for all non-lifetime cadences
  - weekly periods use ISO week numbers (1..53); monthly 1..12; quarterly 1..4; yearly single period 1
  - lifetime uses award_year = -1, award_period = -1 (per model defaults)
  - auto_filters structure: {"include": [{"event_type_id": [..]}, {"event_tag_id": [..]}],
                             "exclude": [...] }
       * We treat each dict in include as a dimension constraint (AND across dimensions, OR within values)
       * Exclude removes events matching ANY of its value lists.
    - Supported threshold types: 'posts' (attendance count),
                                                             'unique_aos' (distinct EventInstanceExpanded.ao_org_id),
                                                             'qs' (number of times user Q'd),
                                                             'posts_at_ao' (attendance at a specific AO or any AO)
  - Additional threshold types can be added by extending _build_metric_clause.

If filter keys are unrecognised, they are ignored (logged at DEBUG level).
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from f3_data_models.models import Achievement, Achievement_x_User
from f3_data_models.utils import get_session
from sqlalchemy import Integer, and_, distinct, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from utilities.database.orm.views import EventAttendance, EventInstanceExpanded

# ---------------------------------------------------------------------------
# Period calculations
# ---------------------------------------------------------------------------


def _daterange_year(year: int) -> Tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday


def _iso_week_range(year: int, iso_week: int) -> Tuple[date, date]:
    # ISO weeks: find first week containing Jan 4 (always week 1)
    jan4 = date(year, 1, 4)
    week1_start = _week_start(jan4)
    start = week1_start + timedelta(weeks=iso_week - 1)
    end = start + timedelta(days=6)
    return start, end


def _month_range(year: int, month: int) -> Tuple[date, date]:
    if month == 12:
        return date(year, 12, 1), date(year, 12, 31)
    start = date(year, month, 1)
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    return start, next_month - timedelta(days=1)


def _quarter_range(year: int, quarter: int) -> Tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    end_month = start_month + 2
    end = _month_range(year, end_month)[1]
    return start, end


def iter_periods(cadence: str, year: int, today: date) -> Iterable[Tuple[int, Tuple[date, date]]]:
    """Yield (period_number, (start, end)) for all periods in [start_of_year, today]."""
    if cadence == "weekly":
        current_week = today.isocalendar().week
        for w in range(1, current_week + 1):
            yield w, _iso_week_range(year, w)
    elif cadence == "monthly":
        for m in range(1, today.month + 1):
            yield m, _month_range(year, m)
    elif cadence == "quarterly":
        current_quarter = (today.month - 1) // 3 + 1
        for q in range(1, current_quarter + 1):
            yield q, _quarter_range(year, q)
    elif cadence == "yearly":
        # Single period = 1 spanning the year to date
        start, _ = _daterange_year(year)
        yield 1, (start, today)
    elif cadence == "lifetime":
        # Represent no bounded date range (None, None) sentinel
        yield -1, (date.min, date.max)
    else:
        raise ValueError(f"Unsupported cadence: {cadence}")


# ---------------------------------------------------------------------------
# Filter & metric helpers
# ---------------------------------------------------------------------------


SUPPORTED_THRESHOLD_TYPES = {"posts", "unique_aos", "qs", "posts_at_ao"}


def _apply_filters(base_filters: list, auto_filters: Dict[str, Any]) -> tuple[list, bool, bool, list, list]:
    """Return (filters, need_type_join, need_tag_join, exclude_type_ids, exclude_tag_ids)."""
    if not auto_filters:
        return base_filters, False, False, [], []
    includes = auto_filters.get("include") or []
    excludes = auto_filters.get("exclude") or []

    include_type_ids: set[int] = set()
    include_tag_ids: set[int] = set()
    exclude_type_ids: set[int] = set()
    exclude_tag_ids: set[int] = set()

    # Collect include constraints
    for inc in includes:
        if not isinstance(inc, dict):
            continue
        type_ids = inc.get("event_type_id") or []
        tag_ids = inc.get("event_tag_id") or []
        include_type_ids.update([tid for tid in type_ids if isinstance(tid, int)])
        include_tag_ids.update([tg for tg in tag_ids if isinstance(tg, int)])
        first_f_ind = inc.get("first_f_ind")
        if first_f_ind is not None:
            base_filters.append(EventInstanceExpanded.first_f_ind == first_f_ind)
        second_f_ind = inc.get("second_f_ind")
        if second_f_ind is not None:
            base_filters.append(EventInstanceExpanded.second_f_ind == second_f_ind)
        third_f_ind = inc.get("third_f_ind")
        if third_f_ind is not None:
            base_filters.append(EventInstanceExpanded.third_f_ind == third_f_ind)
        ao_org_id = inc.get("ao_org_id")
        if ao_org_id is not None:
            base_filters.append(EventInstanceExpanded.ao_org_id == ao_org_id)

    # Collect exclude constraints
    for exc in excludes:
        if not isinstance(exc, dict):
            continue
        type_ids = exc.get("event_type_id") or []
        tag_ids = exc.get("event_tag_id") or []
        exclude_type_ids.update([tid for tid in type_ids if isinstance(tid, int)])
        exclude_tag_ids.update([tg for tg in tag_ids if isinstance(tg, int)])
        first_f_ind = exc.get("first_f_ind")
        if first_f_ind is not None:
            base_filters.append(EventInstanceExpanded.first_f_ind != first_f_ind)
        second_f_ind = exc.get("second_f_ind")
        if second_f_ind is not None:
            base_filters.append(EventInstanceExpanded.second_f_ind != second_f_ind)
        third_f_ind = exc.get("third_f_ind")
        if third_f_ind is not None:
            base_filters.append(EventInstanceExpanded.third_f_ind != third_f_ind)
        ao_org_id = exc.get("ao_org_id")
        if ao_org_id is not None:
            base_filters.append(EventInstanceExpanded.ao_org_id != ao_org_id)

    # When using the flattened views, we no longer need separate joins
    # for type / tag link tables, so the booleans are always False.
    # For now, event_type_id / event_tag_id-based filters are not
    # supported directly against the view and are ignored (but the
    # first/second/third_f_ind filters above are applied normally).

    return base_filters, False, False, list(exclude_type_ids), list(exclude_tag_ids)


def _build_metric_columns(threshold_type: str):
    if threshold_type == "posts":
        return func.count(EventAttendance.id)
    if threshold_type == "unique_aos":
        return func.count(distinct(EventInstanceExpanded.ao_org_id))
    if threshold_type == "qs":
        # Number of times the user Q'd (q_ind is 1 for Q, 0/NULL otherwise)
        return func.coalesce(func.sum(EventAttendance.q_ind), 0)
    if threshold_type == "posts_at_ao":
        # Posts scoped by AO via auto_filters (ao_org_id); when no ao_org_id
        # filter is supplied, this becomes equivalent to total posts.
        return func.count(EventAttendance.id)
    raise ValueError(f"Unsupported auto_threshold_type: {threshold_type}")


def _compute_all_period_metrics(
    session: Session, achievement: Achievement, threshold_type: str, today: date
) -> list[tuple[int, int, int]]:
    """Return list of (user_id, award_year, award_period, metric).

    Single query per achievement to cover all elapsed periods in current year (or lifetime).
    """
    print(f"Computing metrics for achievement={achievement.id} ({threshold_type})...")
    metric_col = _build_metric_columns(threshold_type)
    cadence = str(achievement.auto_cadence.name).lower()

    # Lifetime: group to a fixed (-1, -1)
    if cadence == "lifetime":
        filters: list = []
        filters, need_type_join, need_tag_join, *_ = _apply_filters([], achievement.auto_filters or {})
        if achievement.specific_org_id:
            filters.append(EventAttendance.home_region_id == achievement.specific_org_id)
        query = select(
            EventAttendance.user_id.label("user_id"),
            func.cast(func.literal(-1), Integer).label("award_year"),
            func.cast(func.literal(-1), Integer).label("award_period"),
            metric_col.label("metric"),
        ).join(
            EventInstanceExpanded,
            EventInstanceExpanded.id == EventAttendance.event_instance_id,
        )
        query = query.filter(*filters).group_by("user_id")
        return [(r[0], r[1], r[2], int(r[3])) for r in session.execute(query).all()]

    # Non-lifetime: restrict to year start..today
    year = today.year
    start_year = date(year, 1, 1)
    filters: list = [and_(EventInstanceExpanded.start_date >= start_year, EventInstanceExpanded.start_date <= today)]
    filters, need_type_join, need_tag_join, *_ = _apply_filters(filters, achievement.auto_filters or {})
    if achievement.specific_org_id:
        filters.append(EventAttendance.home_region_id == achievement.specific_org_id)

    # Period expression
    if cadence == "weekly":
        period_expr = func.extract("isoweek", EventInstanceExpanded.start_date)
    elif cadence == "monthly":
        period_expr = func.extract("month", EventInstanceExpanded.start_date)
    elif cadence == "quarterly":
        period_expr = (func.extract("month", EventInstanceExpanded.start_date) - 1) / 3 + 1
    elif cadence == "yearly":
        period_expr = 1
    else:
        raise ValueError(f"Unsupported cadence: {cadence}")

    query = select(
        EventAttendance.user_id.label("user_id"),
        func.cast(year, Integer).label("award_year"),
        func.cast(period_expr, Integer).label("award_period"),
        metric_col.label("metric"),
    ).join(
        EventInstanceExpanded,
        EventInstanceExpanded.id == EventAttendance.event_instance_id,
    )
    query = query.filter(*filters).group_by("user_id", "award_period")
    rows = session.execute(query).all()
    # Filter out future periods (e.g., if partial query produced future periods due to date overlap) - defensive
    valid_rows: list[tuple[int, int, int, int]] = []
    if cadence == "weekly":
        current_week = today.isocalendar().week
        for r in rows:
            if 1 <= r[2] <= current_week:
                valid_rows.append((r[0], r[1], r[2], int(r[3])))
    elif cadence == "monthly":
        for r in rows:
            if 1 <= r[2] <= today.month:
                valid_rows.append((r[0], r[1], r[2], int(r[3])))
    elif cadence == "quarterly":
        current_q = (today.month - 1) // 3 + 1
        for r in rows:
            if 1 <= r[2] <= current_q:
                valid_rows.append((r[0], r[1], r[2], int(r[3])))
    elif cadence == "yearly":
        for r in rows:
            if r[2] == 1:
                valid_rows.append((r[0], r[1], r[2], int(r[3])))
    return valid_rows


# ---------------------------------------------------------------------------
# Core awarding logic
# ---------------------------------------------------------------------------


@dataclass
class CandidateAward:
    achievement_id: int
    user_id: int
    award_year: int
    award_period: int
    metric: int


def _existing_awards(session: Session, achievement_id: int, year: int, period: int) -> set[int]:
    q = select(Achievement_x_User.user_id).filter(
        Achievement_x_User.achievement_id == achievement_id,
        Achievement_x_User.award_year == year,
        Achievement_x_User.award_period == period,
    )
    return {r[0] for r in session.execute(q).all()}


def process_achievement(session: Session, achievement: Achievement, today: date) -> List[CandidateAward]:
    if not achievement.auto_award or not achievement.is_active:
        return []
    if not achievement.auto_threshold or not achievement.auto_threshold_type:
        return []

    threshold_type = str(achievement.auto_threshold_type.name).lower()
    if threshold_type not in SUPPORTED_THRESHOLD_TYPES:
        return []

    all_rows = _compute_all_period_metrics(session, achievement, threshold_type, today)
    if not all_rows:
        return []

    # Collect unique (year, period)
    period_keys = {(r[1], r[2]) for r in all_rows}

    # Prefetch all existing awards for this achievement & these periods
    existing_map: dict[tuple[int, int], set[int]] = {k: set() for k in period_keys}
    period_list = list(period_keys)
    if period_list:
        existing_query = (
            select(
                Achievement_x_User.user_id,
                Achievement_x_User.award_year,
                Achievement_x_User.award_period,
            )
            .filter(Achievement_x_User.achievement_id == achievement.id)
            .filter(tuple_(Achievement_x_User.award_year, Achievement_x_User.award_period).in_(list(period_keys)))
        )
        # Note: Using period_keys directly inside IN since SQLAlchemy will expand tuple set properly.
        # If dialect issues arise, replace with list(year_period_tuples).
        for user_id, y, p in session.execute(existing_query).all():
            existing_map.setdefault((y, p), set()).add(user_id)

    awards: list[CandidateAward] = []
    for user_id, award_year, award_period, metric in all_rows:
        if metric >= achievement.auto_threshold and user_id not in existing_map.get((award_year, award_period), set()):
            awards.append(
                CandidateAward(
                    achievement_id=achievement.id,
                    user_id=user_id,
                    award_year=award_year,
                    award_period=award_period,
                    metric=metric,
                )
            )
    return awards


def award_candidates(session: Session, candidates: Sequence[CandidateAward], dry_run: bool) -> None:
    """Persist awards efficiently.

    Uses a single bulk INSERT .. ON CONFLICT DO NOTHING for Postgres to avoid per-row round trips.
    Falls back to no-op when dry-run.
    """
    if not candidates:
        return
    if dry_run:
        for c in candidates:
            print(
                "[DRY-RUN] Would award achievement="
                f"{c.achievement_id} user={c.user_id} year={c.award_year} "
                f"period={c.award_period} metric={c.metric}"
            )
        print(f"[DRY-RUN] Total new awards: {len(candidates)}")
        return

    now = datetime.now(UTC).date()
    rows = [
        {
            "achievement_id": c.achievement_id,
            "user_id": c.user_id,
            "award_year": c.award_year,
            "award_period": c.award_period,
            "date_awarded": now,
        }
        for c in candidates
    ]

    # Bulk insert with ON CONFLICT DO NOTHING (composite PK prevents duplicates in races)
    stmt = pg_insert(Achievement_x_User).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[
            Achievement_x_User.achievement_id,
            Achievement_x_User.user_id,
            Achievement_x_User.award_year,
            Achievement_x_User.award_period,
        ]
    )
    result = session.execute(stmt)
    session.commit()

    inserted = result.rowcount if result.rowcount is not None else 0
    print(f"Inserted {inserted} new achievement awards (requested {len(rows)}).")
    if inserted < len(rows):
        print("Some awards already existed and were skipped.")


def main():  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description="Auto-award achievements")
    parser.add_argument("--achievement-id", type=int, help="Process only a single achievement id", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Do not persist, only log actions")
    parser.add_argument(
        "--today", type=str, help="Override today's date (YYYY-MM-DD, UTC) for backfilling / testing", default=None
    )
    args = parser.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else datetime.now(UTC).date()

    with get_session() as session:
        ach_query = select(Achievement).filter(Achievement.auto_award.is_(True), Achievement.is_active.is_(True))
        if args.achievement_id:
            ach_query = ach_query.filter(Achievement.id == args.achievement_id)
        achievements = session.scalars(ach_query).all()
        print(f"Processing {len(achievements)} achievements...")
        total_candidates = 0
        for ach in achievements:
            cands = process_achievement(session, ach, today)
            award_candidates(session, cands, args.dry_run)
            total_candidates += len(cands)
        print(f"Done. Candidates processed: {total_candidates}")


if __name__ == "__main__":  # pragma: no cover
    main()

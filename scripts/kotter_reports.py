"""Weekly "Kotter report" runner.

Ports the engagement / fall-off report from the deprecated WeaselBot service
(see github.com/F3-Nation/archive-weaselbot) onto the F3 Nation data model.

For each region that has enabled Site Q (Kotter) reports in settings, this
builds a weekly digest of three groups of PAX and posts it to the region's
configured channel/user (``default_siteq``):

1. PAX who have not posted in a while (MIA).
2. PAX who have Q'd before but not recently (low Q).
3. PAX who post but have never Q'd in the lookback window.

Thresholds (in weeks) come from the region's settings, mirroring WeaselBot:

* ``NO_POST_THRESHOLD``    - a post older than this flags the PAX as MIA.
* ``NO_Q_THRESHOLD_POSTS`` - a last-Q older than this flags low Q.
* ``NO_Q_THRESHOLD_WEEKS`` - lookback for the never-Q'd group.
* ``REMINDER_WEEKS``       - outer lookback; PAX inactive longer than this are
  not surfaced (they have effectively churned).

The report is scheduled weekly via the hourly runner; ``send_kotter_reports``
only acts on ``KOTTER_REPORT_WEEKDAY`` / ``KOTTER_REPORT_HOUR_CST`` unless
called with ``force=True``.
"""

import os
import ssl
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional

import pytz
from f3_data_models.models import SlackSpace, SlackUser
from f3_data_models.utils import DbManager, get_session
from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient
from sqlalchemy import case, func, select

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from utilities.database.orm import SlackSettings
from utilities.database.orm.views import EventAttendance, EventInstanceExpanded
from utilities.helper_functions import current_date_cst, safe_get

# Default thresholds (weeks) used when a region has not customized them.
# These match WeaselBot's documented defaults.
DEFAULT_NO_POST_THRESHOLD = 2
DEFAULT_NO_Q_THRESHOLD_POSTS = 4
DEFAULT_NO_Q_THRESHOLD_WEEKS = 4
DEFAULT_REMINDER_WEEKS = 8

# Weekly schedule (US/Central). The hourly runner invokes this every hour, so
# the report only fires when both match (Sunday @ 6pm CST by default).
KOTTER_REPORT_WEEKDAY = 6  # Monday=0 ... Sunday=6
KOTTER_REPORT_HOUR_CST = 18


@dataclass
class KotterThresholds:
    no_post_threshold: int = DEFAULT_NO_POST_THRESHOLD
    no_q_threshold_posts: int = DEFAULT_NO_Q_THRESHOLD_POSTS
    no_q_threshold_weeks: int = DEFAULT_NO_Q_THRESHOLD_WEEKS
    reminder_weeks: int = DEFAULT_REMINDER_WEEKS

    @classmethod
    def from_settings(cls, settings: SlackSettings) -> "KotterThresholds":
        return cls(
            no_post_threshold=settings.NO_POST_THRESHOLD or DEFAULT_NO_POST_THRESHOLD,
            no_q_threshold_posts=settings.NO_Q_THRESHOLD_POSTS or DEFAULT_NO_Q_THRESHOLD_POSTS,
            no_q_threshold_weeks=settings.NO_Q_THRESHOLD_WEEKS or DEFAULT_NO_Q_THRESHOLD_WEEKS,
            reminder_weeks=settings.REMINDER_WEEKS or DEFAULT_REMINDER_WEEKS,
        )


@dataclass
class PaxActivity:
    """A PAX's posting/Q activity within a region's lookback window."""

    user_id: int
    name: str
    slack_id: Optional[str]
    first_post: date
    last_post: date
    last_q: Optional[date]
    q_count: int


@dataclass
class KotterBuckets:
    mia: List[PaxActivity] = field(default_factory=list)
    low_q: List[PaxActivity] = field(default_factory=list)
    never_q: List[PaxActivity] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.mia or self.low_q or self.never_q)


def classify_pax(activities: List[PaxActivity], today: date, thresholds: KotterThresholds) -> KotterBuckets:
    """Sort PAX into the MIA / low-Q / never-Q groups.

    The three groups are computed independently and then de-overlapped (a PAX
    is reported in at most one group, MIA taking precedence, then low-Q),
    mirroring WeaselBot's behavior. Pure function (no I/O) so the bucketing
    rules can be unit tested.
    """
    reminder_floor = today - timedelta(weeks=thresholds.reminder_weeks)
    mia_cutoff = today - timedelta(weeks=thresholds.no_post_threshold)
    low_q_cutoff = today - timedelta(weeks=thresholds.no_q_threshold_posts)
    never_q_cutoff = today - timedelta(weeks=thresholds.no_q_threshold_weeks)

    # Only consider PAX with activity inside the outer reminder window; older
    # than that and they have effectively churned.
    active = [p for p in activities if p.last_post >= reminder_floor]

    # MIA: no post within the no-post threshold.
    mia = [p for p in active if p.last_post <= mia_cutoff]
    mia_ids = {p.user_id for p in mia}

    # Low Q: has Q'd within the window but not recently. Excludes MIA.
    low_q = [
        p
        for p in active
        if p.user_id not in mia_ids and p.q_count > 0 and p.last_q is not None and p.last_q <= low_q_cutoff
    ]
    low_q_ids = {p.user_id for p in low_q}

    # Never Q: posting (not MIA) for at least the threshold but no Q in window.
    never_q = [
        p
        for p in active
        if p.user_id not in mia_ids
        and p.user_id not in low_q_ids
        and p.q_count == 0
        and p.first_post <= never_q_cutoff
    ]

    buckets = KotterBuckets(
        mia=sorted(mia, key=lambda p: p.last_post),
        low_q=sorted(low_q, key=lambda p: p.last_q or date.min),
        never_q=sorted(never_q, key=lambda p: p.last_post),
    )
    return buckets


def _mention(pax: PaxActivity) -> str:
    return f"<@{pax.slack_id}>" if pax.slack_id else (pax.name or "Unknown PAX")


def build_kotter_message(region_name: str, site_q: Optional[str], buckets: KotterBuckets, today: date) -> str:
    """Render the Slack message for a region's Kotter report."""
    greeting = f"Howdy{f', <@{site_q}>' if site_q else ''}! Here is your weekly Site Q report"
    lines = [f"{greeting} for *{region_name}*. According to my records..."]

    if buckets.mia:
        lines.append("\n\n*These PAX haven't posted in a while:*")
        for pax in buckets.mia:
            lines.append(f"\n- {_mention(pax)} last posted {pax.last_post.strftime('%B %d, %Y')}")

    if buckets.low_q:
        lines.append("\n\n*These PAX haven't Q'd in a while. Here's how long it's been:*")
        for pax in buckets.low_q:
            days = (today - pax.last_q).days if pax.last_q else 0
            lines.append(f"\n- {_mention(pax)}: {days} days")

    if buckets.never_q:
        lines.append("\n\n*These PAX have been posting but have never Q'd:*")
        for pax in buckets.never_q:
            lines.append(f"\n- {_mention(pax)}")

    return "".join(lines)


def _get_ssl_context() -> ssl.SSLContext:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def _pull_region_activity(session, org_id: int, team_id: str, reminder_weeks: int, today: date) -> List[PaxActivity]:
    """Aggregate each PAX's posting/Q activity for a region's lookback window."""
    window_start = today - timedelta(weeks=reminder_weeks)

    q_date = case((EventAttendance.q_ind == 1, EventInstanceExpanded.start_date), else_=None)
    query = (
        select(
            EventAttendance.user_id,
            func.max(EventAttendance.f3_name).label("name"),
            func.min(EventInstanceExpanded.start_date).label("first_post"),
            func.max(EventInstanceExpanded.start_date).label("last_post"),
            func.max(q_date).label("last_q"),
            func.coalesce(func.sum(EventAttendance.q_ind), 0).label("q_count"),
        )
        .join(EventInstanceExpanded, EventInstanceExpanded.id == EventAttendance.event_instance_id)
        .where(
            EventInstanceExpanded.region_org_id == org_id,
            EventInstanceExpanded.start_date >= window_start,
            EventInstanceExpanded.start_date <= today,
        )
        .group_by(EventAttendance.user_id)
    )
    rows = session.execute(query).all()
    if not rows:
        return []

    # Map user_id -> slack_id for this region's workspace.
    user_ids = [r.user_id for r in rows]
    slack_users = session.scalars(
        select(SlackUser).where(SlackUser.user_id.in_(user_ids), SlackUser.slack_team_id == team_id)
    ).all()
    slack_id_by_user = {su.user_id: su.slack_id for su in slack_users}

    def _as_date(value):
        return value.date() if isinstance(value, datetime) else value

    activities: List[PaxActivity] = []
    for r in rows:
        activities.append(
            PaxActivity(
                user_id=r.user_id,
                name=r.name or "Unknown PAX",
                slack_id=slack_id_by_user.get(r.user_id),
                first_post=_as_date(r.first_post),
                last_post=_as_date(r.last_post),
                last_q=_as_date(r.last_q),
                q_count=int(r.q_count or 0),
            )
        )
    return activities


def _post_report(client: WebClient, channel: str, text: str) -> None:
    """Post the report, joining the channel first if needed."""
    try:
        client.chat_postMessage(channel=channel, text=text, link_names=True)
    except SlackApiError as e:
        if e.response.get("error") == "not_in_channel":
            try:
                client.conversations_join(channel=channel)
                client.chat_postMessage(channel=channel, text=text, link_names=True)
            except Exception as join_error:
                print(f"[{channel}] Could not join channel to post Kotter report: {join_error}")
        else:
            print(f"[{channel}] Error posting Kotter report: {e}")


def send_kotter_reports(force: bool = False, dry_run: bool = False) -> None:
    """Build and send weekly Kotter reports for all opted-in regions."""
    current_time = datetime.now(pytz.timezone("US/Central"))
    if not force and not (
        current_time.weekday() == KOTTER_REPORT_WEEKDAY and current_time.hour == KOTTER_REPORT_HOUR_CST
    ):
        return

    slack_spaces = DbManager.find_records(SlackSpace, filters=[True])
    today = current_date_cst()
    session = get_session()
    ssl_context = _get_ssl_context()

    for slack_space in slack_spaces:
        if not slack_space.settings or not safe_get(slack_space.settings, "org_id"):
            continue
        settings = SlackSettings(**slack_space.settings)

        # Region must have opted in and configured a destination.
        if not settings.send_aoq_reports or not settings.default_siteq:
            continue

        thresholds = KotterThresholds.from_settings(settings)
        activities = _pull_region_activity(
            session, settings.org_id, settings.team_id, thresholds.reminder_weeks, today
        )
        buckets = classify_pax(activities, today, thresholds)
        if buckets.is_empty:
            print(f"[{settings.team_id}] No Kotter report items. Skipping.")
            continue

        region_name = settings.workspace_name or "your region"
        message = build_kotter_message(region_name, settings.default_siteq, buckets, today)

        if dry_run:
            print(f"[DRY-RUN] [{settings.team_id}] Would post Kotter report:\n{message}\n")
            continue

        if not settings.bot_token:
            print(f"[{settings.team_id}] No bot token available. Skipping.")
            continue

        client = WebClient(settings.bot_token, ssl=ssl_context)
        _post_report(client, settings.default_siteq, message)
        print(f"[{settings.team_id}] Sent Kotter report to {settings.default_siteq}.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send weekly Kotter (Site Q) reports")
    parser.add_argument("--force", action="store_true", help="Ignore the weekly schedule and run now")
    parser.add_argument("--dry-run", action="store_true", help="Print reports instead of posting to Slack")
    args = parser.parse_args()

    send_kotter_reports(force=args.force, dry_run=args.dry_run)

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.kotter_reports import (
    KotterThresholds,
    PaxActivity,
    build_kotter_message,
    classify_pax,
)

TODAY = date(2026, 6, 8)
# Default thresholds (weeks): no_post=2, no_q_posts=4, no_q_weeks=4, reminder=8
#   reminder_floor = 2026-04-13, mia_cutoff = 2026-05-25,
#   low_q_cutoff = never_q_cutoff = 2026-05-11
THRESHOLDS = KotterThresholds()


def _pax(user_id, first_post, last_post, last_q=None, q_count=0, slack_id=None, name="PAX"):
    return PaxActivity(
        user_id=user_id,
        name=name,
        slack_id=slack_id,
        first_post=first_post,
        last_post=last_post,
        last_q=last_q,
        q_count=q_count,
    )


class TestClassifyPax(unittest.TestCase):
    def test_mia_flagged_when_no_recent_post(self):
        pax = _pax(1, first_post=date(2026, 4, 20), last_post=date(2026, 5, 20))
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertEqual([p.user_id for p in buckets.mia], [1])
        self.assertFalse(buckets.low_q or buckets.never_q)

    def test_churned_pax_ignored(self):
        # Last post older than the reminder window -> not surfaced at all.
        pax = _pax(2, first_post=date(2026, 1, 1), last_post=date(2026, 3, 1))
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertTrue(buckets.is_empty)

    def test_low_q_flagged_for_lapsed_q(self):
        # Posting recently (not MIA) but last Q was well over the threshold.
        pax = _pax(3, first_post=date(2026, 4, 15), last_post=date(2026, 6, 6), last_q=date(2026, 5, 1), q_count=3)
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertEqual([p.user_id for p in buckets.low_q], [3])
        self.assertFalse(buckets.mia or buckets.never_q)

    def test_never_q_flagged_for_regular_poster(self):
        # Posts regularly (incl. recently), around long enough, but never Q'd.
        pax = _pax(4, first_post=date(2026, 4, 20), last_post=date(2026, 6, 7), q_count=0)
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertEqual([p.user_id for p in buckets.never_q], [4])
        self.assertFalse(buckets.mia or buckets.low_q)

    def test_active_qer_not_flagged(self):
        pax = _pax(5, first_post=date(2026, 4, 20), last_post=date(2026, 6, 7), last_q=date(2026, 6, 6), q_count=5)
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertTrue(buckets.is_empty)

    def test_brand_new_never_q_not_flagged(self):
        # First post within the never-Q threshold -> too new to nudge.
        pax = _pax(6, first_post=date(2026, 6, 1), last_post=date(2026, 6, 7), q_count=0)
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertTrue(buckets.is_empty)

    def test_groups_are_mutually_exclusive(self):
        # An MIA PAX who also lapsed on Q only appears under MIA.
        pax = _pax(7, first_post=date(2026, 4, 15), last_post=date(2026, 5, 18), last_q=date(2026, 4, 20), q_count=2)
        buckets = classify_pax([pax], TODAY, THRESHOLDS)
        self.assertEqual([p.user_id for p in buckets.mia], [7])
        self.assertFalse(buckets.low_q or buckets.never_q)


class TestBuildKotterMessage(unittest.TestCase):
    def test_message_includes_each_group_and_mentions(self):
        buckets = classify_pax(
            [
                _pax(1, date(2026, 4, 20), date(2026, 5, 20), slack_id="U1"),
                _pax(3, date(2026, 4, 15), date(2026, 6, 6), last_q=date(2026, 5, 1), q_count=3, slack_id="U3"),
                _pax(4, date(2026, 4, 20), date(2026, 6, 7), q_count=0, slack_id="U4"),
            ],
            TODAY,
            THRESHOLDS,
        )
        msg = build_kotter_message("F3 Tornado Alley", "U999", buckets, TODAY)
        self.assertIn("F3 Tornado Alley", msg)
        self.assertIn("<@U999>", msg)  # Site Q greeting
        self.assertIn("<@U1>", msg)  # MIA
        self.assertIn("<@U3>", msg)  # low Q (with day count)
        self.assertIn("<@U4>", msg)  # never Q
        self.assertIn("haven't posted", msg)
        self.assertIn("haven't Q'd", msg)
        self.assertIn("never Q'd", msg)

    def test_falls_back_to_name_without_slack_id(self):
        buckets = classify_pax([_pax(1, date(2026, 4, 20), date(2026, 5, 20), name="Greco")], TODAY, THRESHOLDS)
        msg = build_kotter_message("Region", None, buckets, TODAY)
        self.assertIn("Greco", msg)


if __name__ == "__main__":
    unittest.main()

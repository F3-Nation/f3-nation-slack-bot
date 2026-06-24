import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from features import achievements
from utilities.database.orm import SlackSettings


def _make_region_record(org_id=10, send_achievements=None):
    return SlackSettings(team_id="T123", org_id=org_id, send_achievements=send_achievements)


class TestAchievementsEnabledForRegion(unittest.TestCase):
    """Unit tests for the per-region achievements opt-in gate."""

    def test_disabled_by_default(self):
        # A region that is neither in the alpha allowlist nor opted in has no access.
        with patch.object(achievements, "ACHIEVEMENTS_ALPHA_TESTING_ORG_IDS", []):
            record = _make_region_record(org_id=10, send_achievements=None)
            self.assertFalse(achievements.achievements_enabled_for_region(record))

    def test_enabled_via_region_opt_in(self):
        # Enabling achievements in region settings (send_achievements) grants access.
        with patch.object(achievements, "ACHIEVEMENTS_ALPHA_TESTING_ORG_IDS", []):
            record = _make_region_record(org_id=10, send_achievements=1)
            self.assertTrue(achievements.achievements_enabled_for_region(record))

    def test_enabled_via_alpha_allowlist_override(self):
        # The env-var allowlist remains a force-enable override even without opt-in.
        with patch.object(achievements, "ACHIEVEMENTS_ALPHA_TESTING_ORG_IDS", [10]):
            record = _make_region_record(org_id=10, send_achievements=None)
            self.assertTrue(achievements.achievements_enabled_for_region(record))

    def test_opt_out_disables_for_non_alpha_org(self):
        # send_achievements explicitly off (0) keeps a non-alpha region gated.
        with patch.object(achievements, "ACHIEVEMENTS_ALPHA_TESTING_ORG_IDS", [99]):
            record = _make_region_record(org_id=10, send_achievements=0)
            self.assertFalse(achievements.achievements_enabled_for_region(record))


if __name__ == "__main__":
    unittest.main()

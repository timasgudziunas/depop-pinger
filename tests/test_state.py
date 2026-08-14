"""Unit tests for state.py. Run with: python -m unittest tests.test_state
or: python tests/test_state.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "seen_listings.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_seen_missing_file_returns_empty_dict(self):
        self.assertEqual(state.load_seen(self.path), {})

    def test_round_trip_save_and_load(self):
        seen = {}
        state.mark_seen("listing-1", seen)
        state.save_seen(seen, self.path)

        reloaded = state.load_seen(self.path)
        self.assertIn("listing-1", reloaded)

    def test_is_new_true_for_unseen_id(self):
        seen = {}
        self.assertTrue(state.is_new("listing-1", seen))

    def test_is_new_false_after_mark_seen(self):
        seen = {}
        state.mark_seen("listing-1", seen)
        self.assertFalse(state.is_new("listing-1", seen))

    def test_mark_seen_does_not_overwrite_existing_timestamp(self):
        seen = {"listing-1": "2020-01-01T00:00:00+00:00"}
        state.mark_seen("listing-1", seen)
        self.assertEqual(seen["listing-1"], "2020-01-01T00:00:00+00:00")

    def test_save_seen_prunes_entries_older_than_retention(self):
        now = datetime.now(timezone.utc)
        old_timestamp = (now - timedelta(days=state.config.SEEN_RETENTION_DAYS + 1)).isoformat()
        recent_timestamp = (now - timedelta(days=1)).isoformat()
        seen = {
            "old-listing": old_timestamp,
            "recent-listing": recent_timestamp,
        }
        state.save_seen(seen, self.path)

        reloaded = state.load_seen(self.path)
        self.assertNotIn("old-listing", reloaded)
        self.assertIn("recent-listing", reloaded)

    def test_save_seen_keeps_entry_just_inside_retention_boundary(self):
        # A few seconds shy of the exact cutoff, comfortably inside the
        # retention window regardless of the small delay between computing
        # this timestamp and save_seen() computing its own cutoff.
        now = datetime.now(timezone.utc)
        boundary_timestamp = (
            now - timedelta(days=state.config.SEEN_RETENTION_DAYS) + timedelta(seconds=30)
        ).isoformat()
        seen = {"boundary-listing": boundary_timestamp}
        state.save_seen(seen, self.path)

        reloaded = state.load_seen(self.path)
        self.assertIn("boundary-listing", reloaded)

    def test_corrupt_json_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with self.assertRaises(json.JSONDecodeError):
            state.load_seen(self.path)


if __name__ == "__main__":
    unittest.main()

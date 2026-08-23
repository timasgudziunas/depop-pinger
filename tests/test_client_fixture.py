"""Fixture-driven tests tying depop_client normalization to filters.py
against a real saved Depop search response. Run with:
python -m unittest tests.test_client_fixture or: python tests/test_client_fixture.py
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from depop_client import _normalize_product
from filters import matches_criteria

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "search_response.json")


def _load_fixture_objects() -> list[dict]:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["objects"]


class TestNormalizedFixtureKeys(unittest.TestCase):
    def test_every_listing_has_new_keys(self):
        objects = _load_fixture_objects()
        self.assertGreater(len(objects), 0)
        listings = [_normalize_product(obj) for obj in objects]
        for listing in listings:
            self.assertIn("country", listing)
            self.assertIn("condition", listing)
            self.assertIn("is_kids", listing)


class TestFixtureAgainstRealConfig(unittest.TestCase):
    """Runs the full fixture through matches_criteria with pure config
    defaults (no overrides) and asserts on concrete, empirically-verified
    counts so this test is deterministic. See depop-pinger's CLAUDE.md for
    the real criteria (config.py)."""

    @classmethod
    def setUpClass(cls):
        objects = _load_fixture_objects()
        cls.listings = [_normalize_product(obj) for obj in objects]

    def test_no_fixture_listing_passes_real_config(self):
        # Empirically verified 2026-08-23, after the size-0-only revision
        # (CRITERIA.md Q7): NO fixture listing passes the full real config.
        # The two that passed under the 2026-08-17 criteria (865279394 and
        # 859710333) are both size 2, and the fixture's only size-0 listing
        # (863434415) fails on excluded terms ("high rise").
        passing = [l for l in self.listings if matches_criteria(l)]
        self.assertEqual({l["id"] for l in passing}, set())

    def test_former_passers_fail_on_size_alone(self):
        # 865279394 and 859710333 satisfy every OTHER real-config criterion:
        # widening only target_sizes back to include "2" makes exactly these
        # two pass, proving the size filter is the sole reason they now fail.
        widened = ["0", "2", "XS", "XXS", "US 0", "US 2"]
        passing = [l for l in self.listings if matches_criteria(l, target_sizes=widened)]
        self.assertEqual({l["id"] for l in passing}, {"865279394", "859710333"})

    def test_used_good_listing_fails(self):
        used_good = [l for l in self.listings if l.get("condition") == "used_good"]
        self.assertGreater(len(used_good), 0, "fixture should contain a used_good listing")
        for listing in used_good:
            self.assertFalse(matches_criteria(listing))

    def test_wrong_sizes_fail(self):
        # Sizes 2, 4, 6, and S exist in the fixture and are not in
        # config.TARGET_SIZES (size 0 only as of 2026-08-23), so listings
        # with those sizes must fail regardless of other criteria.
        for size in ("2", "4", "6", "S"):
            matching_size = [l for l in self.listings if l.get("size") == size]
            self.assertGreater(len(matching_size), 0, f"fixture should contain a size {size} listing")
            for listing in matching_size:
                self.assertFalse(matches_criteria(listing), f"listing {listing['id']} size={size} should fail")


if __name__ == "__main__":
    unittest.main()

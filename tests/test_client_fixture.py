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

    def test_some_listings_pass_and_some_fail(self):
        results = [matches_criteria(listing) for listing in self.listings]
        passing = [l for l, r in zip(self.listings, results) if r]
        failing = [l for l, r in zip(self.listings, results) if not r]

        self.assertGreater(len(passing), 0, "expected at least one fixture listing to pass")
        self.assertGreater(len(failing), 0, "expected at least one fixture listing to fail")

        # Empirically verified against tests/fixtures/search_response.json,
        # 2026-08-17: exactly these two listings satisfy every criterion in
        # config.py (keyword, exclusions, size in {0,2,XS,XXS,US 0,US 2},
        # price <= 25.0, condition in {brand_new, used_like_new,
        # used_excellent}, country in {US, CA}, not kids).
        passing_ids = {l["id"] for l in passing}
        self.assertEqual(passing_ids, {"865279394", "859710333"})

    def test_used_good_listing_fails(self):
        used_good = [l for l in self.listings if l.get("condition") == "used_good"]
        self.assertGreater(len(used_good), 0, "fixture should contain a used_good listing")
        for listing in used_good:
            self.assertFalse(matches_criteria(listing))

    def test_wrong_sizes_fail(self):
        # Sizes 4, 6, and S exist in the fixture and are not in
        # config.TARGET_SIZES, so listings with those sizes (and otherwise
        # matching config criteria) must fail on size alone.
        for size in ("4", "6", "S"):
            matching_size = [l for l in self.listings if l.get("size") == size]
            self.assertGreater(len(matching_size), 0, f"fixture should contain a size {size} listing")
            for listing in matching_size:
                self.assertFalse(matches_criteria(listing), f"listing {listing['id']} size={size} should fail")


if __name__ == "__main__":
    unittest.main()

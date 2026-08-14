"""Unit tests for filters.py. Run with: python -m unittest tests.test_filters
or: python tests/test_filters.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filters import matches_criteria


def make_listing(size=None, price=20.0):
    return {
        "id": "abc123",
        "title": "Lululemon Speedup Shorts",
        "price": price,
        "currency": "GBP",
        "size": size,
        "url": "https://www.depop.com/products/abc123/",
        "image_url": None,
    }


class TestMatchesCriteria(unittest.TestCase):
    def test_size_match_exact(self):
        listing = make_listing(size="UK 8")
        self.assertTrue(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_match_case_insensitive(self):
        listing = make_listing(size="uk 8")
        self.assertTrue(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_mismatch(self):
        listing = make_listing(size="UK 10")
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_none_with_criteria_specified_fails(self):
        # A listing with no parsed size does NOT match once sizes are
        # specified -- better to miss an ambiguous listing than spam.
        listing = make_listing(size=None)
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 6", "UK 8"], max_price=None))

    def test_size_none_with_empty_target_sizes_passes(self):
        # Empty TARGET_SIZES means size filtering is skipped entirely, so
        # even an unparsed size passes.
        listing = make_listing(size=None)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_empty_target_sizes_passes_all_sizes(self):
        listing = make_listing(size="XL")
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_price_ceiling_boundary_equal_passes(self):
        listing = make_listing(size=None, price=40.0)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=40.0))

    def test_price_ceiling_boundary_over_fails(self):
        listing = make_listing(size=None, price=40.01)
        self.assertFalse(matches_criteria(listing, target_sizes=[], max_price=40.0))

    def test_price_none_skips_price_check(self):
        listing = make_listing(size=None, price=999.0)
        self.assertTrue(matches_criteria(listing, target_sizes=[], max_price=None))

    def test_both_criteria_must_pass(self):
        listing = make_listing(size="UK 8", price=50.0)
        self.assertFalse(matches_criteria(listing, target_sizes=["UK 8"], max_price=40.0))
        listing_ok = make_listing(size="UK 8", price=30.0)
        self.assertTrue(matches_criteria(listing_ok, target_sizes=["UK 8"], max_price=40.0))

    def test_defaults_to_config_when_not_passed(self):
        # No kwargs passed -> falls back to config.TARGET_SIZES / config.MAX_PRICE,
        # which ship as [] and None (placeholders), so everything should pass.
        listing = make_listing(size=None, price=999.0)
        self.assertTrue(matches_criteria(listing))


if __name__ == "__main__":
    unittest.main()

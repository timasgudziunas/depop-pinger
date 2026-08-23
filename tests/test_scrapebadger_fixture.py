"""Fixture-driven tests tying depop_client's ScrapeBadger normalization to
real saved ScrapeBadger search/detail responses. Run with:
python -m unittest tests.test_scrapebadger_fixture or: python tests/test_scrapebadger_fixture.py
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import depop_client

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEARCH_FIXTURE_PATH = os.path.join(FIXTURES_DIR, "scrapebadger_search.json")
PRODUCT_FIXTURE_PATH = os.path.join(FIXTURES_DIR, "scrapebadger_product.json")

TARGET_SLUG = "vesla_p-size-6-black-lululemon-speedup-75ca"


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _mock_response(status_code: int, json_data):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


class TestScrapeBadgerFixtureNormalization(unittest.TestCase):
    """Runs the real search+product fixtures through the actual ScrapeBadger
    fetch/normalize/merge path (HTTP layer patched to serve them)."""

    def test_first_product_normalizes_as_expected(self):
        search_data = _load(SEARCH_FIXTURE_PATH)
        product_data = _load(PRODUCT_FIXTURE_PATH)
        self.assertEqual(product_data["slug"], TARGET_SLUG)

        search_resp = _mock_response(200, search_data)
        product_resp = _mock_response(200, product_data)

        # Permissive config so the size-6 $45 card survives prefiltering and
        # its detail actually gets fetched -- this test is about the
        # normalization/merge, not the prefilter (see the class below for
        # that, which uses the real, restrictive config on purpose).
        # skip_ids excludes every other card in the fixture so exactly one
        # detail call happens, matching the single product fixture on disk.
        other_slugs = {p["slug"] for p in search_data["products"] if p["slug"] != TARGET_SLUG}

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch.object(config, "TARGET_SIZES", []), \
                mock.patch.object(config, "MAX_PRICE", None), \
                mock.patch.object(config, "MAX_DETAIL_FETCHES_PER_RUN", 25), \
                mock.patch("depop_client.requests.get", side_effect=[search_resp, product_resp]) as mock_get:
            listings = depop_client.fetch_listings(search_data["query"], skip_ids=other_slugs)

        self.assertEqual(mock_get.call_count, 2)  # one search + exactly one detail call
        self.assertEqual(len(listings), 1)
        first = listings[0]

        self.assertEqual(first["id"], TARGET_SLUG)
        self.assertEqual(first["price"], 45.0)
        self.assertEqual(first["size"], "6")
        self.assertEqual(first["currency"], "USD")
        self.assertIsNone(first["condition"])  # raw "UsedCondition" maps to None
        self.assertIsNone(first["country"])  # ScrapeBadger doesn't expose it
        self.assertIn("speedup", first["title"].casefold())
        self.assertTrue(first["url"])
        self.assertTrue(first["image_url"])


class TestScrapeBadgerFixturePrefilterWithRealConfig(unittest.TestCase):
    """Confirms the size-6 $45 card in the fixture would never reach a
    (paid) detail call under the actual shipped config (size 0 only,
    max price $25) -- these assertions deliberately do NOT mock
    config.TARGET_SIZES / config.MAX_PRICE, using the real config.py
    values."""

    def test_size_6_card_fails_the_zero_cost_prefilter(self):
        search_data = _load(SEARCH_FIXTURE_PATH)
        card = next(p for p in search_data["products"] if p["slug"] == TARGET_SLUG)
        self.assertEqual(card["size"], "6")
        self.assertEqual(card["price"], "45.00")

        self.assertNotIn("6", config.TARGET_SIZES)  # sanity: still real, restrictive config
        self.assertFalse(depop_client._card_survives_prefilter(card, skip_ids=set()))

    def test_fetch_listings_with_real_config_never_requests_its_detail(self):
        search_data = _load(SEARCH_FIXTURE_PATH)
        target_card = next(p for p in search_data["products"] if p["slug"] == TARGET_SLUG)
        search_resp = _mock_response(
            200, {"products": [target_card], "meta": {}, "market": "us", "query": search_data["query"]}
        )

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", return_value=search_resp) as mock_get:
            listings = depop_client.fetch_listings(search_data["query"])

        self.assertEqual(listings, [])
        mock_get.assert_called_once()  # search only -- no detail request for this card


if __name__ == "__main__":
    unittest.main()

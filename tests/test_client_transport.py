"""Unit tests for depop_client's transport selection and ScrapeBadger
two-step search+detail fetch. Run with:
python -m unittest tests.test_client_transport or: python tests/test_client_transport.py
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import depop_client


def _mock_response(status_code: int, json_data=None, text: str = ""):
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("no JSON body")
    return response


def _card(slug="a-slug", size="0", price="20.00", is_sold=False, currency="USD"):
    return {
        "slug": slug,
        "url": f"https://www.depop.com/products/{slug}/",
        "seller_username": "seller",
        "brand": "Lululemon",
        "size": size,
        "price": price,
        "original_price": None,
        "currency": currency,
        "is_sold": is_sold,
        "image": f"https://media-photos.depop.com/{slug}/P0.jpg",
    }


def _detail(slug="a-slug", title="lululemon speedup shorts", description=None, condition="UsedCondition"):
    if description is None:
        description = f"{title} some more text #lululemon"
    return {
        "id": 123,
        "slug": slug,
        "title": title,
        "description": description,
        "brand": "Lululemon",
        "condition": condition,
        "price": "20.00",
        "currency": "USD",
        "availability": "InStock",
        "dispatch_time": "24 hours",
        "seller_username": "seller",
        "images": [],
        "url": f"https://www.depop.com/products/{slug}/",
    }


class TestScrapeBadgerHappyPath(unittest.TestCase):
    def test_search_then_detail_normalizes_and_sends_expected_requests(self):
        search_resp = _mock_response(200, {"products": [_card()], "meta": {}, "market": "us", "query": "q"})
        detail_resp = _mock_response(200, _detail(condition="NewCondition"))

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch.object(config, "TARGET_SIZES", ["0"]), \
                mock.patch.object(config, "MAX_PRICE", 25.0), \
                mock.patch.object(config, "MAX_DETAIL_FETCHES_PER_RUN", 8), \
                mock.patch("depop_client.requests.get", side_effect=[search_resp, detail_resp]) as mock_get:
            listings = depop_client.fetch_listings("lululemon speedup shorts")

        self.assertEqual(len(listings), 1)
        listing = listings[0]
        self.assertEqual(listing["id"], "a-slug")
        self.assertEqual(listing["price"], 20.0)
        self.assertIsInstance(listing["price"], float)
        self.assertEqual(listing["condition"], "brand_new")
        self.assertEqual(listing["size"], "0")
        self.assertEqual(listing["currency"], "USD")
        self.assertIsNone(listing["country"])
        self.assertIsNone(listing["is_kids"])

        self.assertEqual(mock_get.call_count, 2)
        search_call, detail_call = mock_get.call_args_list

        search_url = search_call.args[0]
        self.assertEqual(search_url, "https://scrapebadger.com/v1/depop/search")
        self.assertEqual(search_call.kwargs["headers"]["X-API-Key"], "sb_live_test")
        self.assertEqual(search_call.kwargs["params"]["sort"], "newest")
        self.assertEqual(search_call.kwargs["params"]["query"], "lululemon speedup shorts")
        self.assertEqual(search_call.kwargs["params"]["price_max"], 25.0)
        self.assertNotIn("sizes", search_call.kwargs["params"])

        detail_url = detail_call.args[0]
        self.assertEqual(detail_url, "https://scrapebadger.com/v1/depop/products/a-slug")
        self.assertEqual(detail_call.kwargs["headers"]["X-API-Key"], "sb_live_test")


class TestScrapeBadgerPriceMaxParam(unittest.TestCase):
    def test_price_max_absent_when_max_price_none(self):
        search_resp = _mock_response(200, {"products": [], "meta": {}, "market": "us", "query": "q"})

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch.object(config, "MAX_PRICE", None), \
                mock.patch("depop_client.requests.get", return_value=search_resp) as mock_get:
            depop_client.fetch_listings("q")

        search_call = mock_get.call_args_list[0]
        self.assertNotIn("price_max", search_call.kwargs["params"])
        self.assertNotIn("sizes", search_call.kwargs["params"])


class TestScrapeBadgerPrefilter(unittest.TestCase):
    def _run_with_cards(self, cards, skip_ids=None, target_sizes=("0",), max_price=25.0):
        search_resp = _mock_response(200, {"products": cards, "meta": {}, "market": "us", "query": "q"})
        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch.object(config, "TARGET_SIZES", list(target_sizes)), \
                mock.patch.object(config, "MAX_PRICE", max_price), \
                mock.patch.object(config, "MAX_DETAIL_FETCHES_PER_RUN", 8), \
                mock.patch("depop_client.requests.get") as mock_get:
            mock_get.side_effect = [search_resp] + [_mock_response(200, _detail()) for _ in range(len(cards))]
            listings = depop_client.fetch_listings("q", skip_ids=skip_ids)
        return listings, mock_get

    def test_sold_card_produces_no_detail_request(self):
        cards = [_card(slug="sold-one", is_sold=True)]
        listings, mock_get = self._run_with_cards(cards)
        self.assertEqual(listings, [])
        self.assertEqual(mock_get.call_count, 1)  # search only

    def test_wrong_size_card_produces_no_detail_request(self):
        cards = [_card(slug="wrong-size", size="6")]
        listings, mock_get = self._run_with_cards(cards)
        self.assertEqual(listings, [])
        self.assertEqual(mock_get.call_count, 1)

    def test_over_price_card_produces_no_detail_request(self):
        cards = [_card(slug="pricey", price="99.00")]
        listings, mock_get = self._run_with_cards(cards)
        self.assertEqual(listings, [])
        self.assertEqual(mock_get.call_count, 1)

    def test_price_exactly_at_ceiling_survives_prefilter(self):
        # The $25 cap is inclusive at every layer: filters._matches_price
        # (<=), this prefilter (drops only strictly-over), and ScrapeBadger's
        # server-side price_max (verified live 2026-08-25: price_max=25
        # returns $25.00 cards).
        cards = [_card(slug="at-ceiling", price="25.00")]
        listings, mock_get = self._run_with_cards(cards, max_price=25.0)
        self.assertEqual(len(listings), 1)
        self.assertEqual(mock_get.call_count, 2)  # search + detail

    def test_skip_ids_card_produces_no_detail_request(self):
        cards = [_card(slug="already-seen")]
        listings, mock_get = self._run_with_cards(cards, skip_ids={"already-seen"})
        self.assertEqual(listings, [])
        self.assertEqual(mock_get.call_count, 1)

    def test_surviving_card_still_gets_detail_request(self):
        cards = [_card(slug="fresh")]
        listings, mock_get = self._run_with_cards(cards)
        self.assertEqual(len(listings), 1)
        self.assertEqual(mock_get.call_count, 2)


class TestScrapeBadgerRetryAndErrors(unittest.TestCase):
    def test_429_then_200_retries_and_sleeps(self):
        rate_limited = _mock_response(429, {"detail": "Rate limit exceeded", "limit": 5, "remaining": 0, "reset_at": 1000.0, "tier": "free"})
        ok = _mock_response(200, {"products": [], "meta": {}, "market": "us", "query": "q"})

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", side_effect=[rate_limited, ok]) as mock_get, \
                mock.patch("depop_client.time.time", return_value=990.0), \
                mock.patch("depop_client.time.sleep") as mock_sleep:
            listings = depop_client.fetch_listings("q")

        self.assertEqual(listings, [])
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()
        slept_seconds = mock_sleep.call_args.args[0]
        self.assertAlmostEqual(slept_seconds, 10.0, places=3)

    def test_401_raises_value_error(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", return_value=_mock_response(401, text="unauthorized")):
            with self.assertRaises(ValueError):
                depop_client.fetch_listings("q")

    def test_403_raises_value_error(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", return_value=_mock_response(403, text="forbidden")):
            with self.assertRaises(ValueError):
                depop_client.fetch_listings("q")

    def test_502_search_returns_no_listings(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", return_value=_mock_response(502, text="bad gateway")):
            listings = depop_client.fetch_listings("q")
        self.assertEqual(listings, [])

    def test_200_missing_products_key_raises_schema_error(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch("depop_client.requests.get", return_value=_mock_response(200, {"meta": {}})):
            with self.assertRaises(depop_client.DepopResponseSchemaError):
                depop_client.fetch_listings("q")


class TestEmptyKeyUsesDirectPath(unittest.TestCase):
    def test_empty_scraper_key_uses_direct_get(self):
        response = mock.Mock(status_code=200, text="<html>direct</html>")
        with mock.patch.object(config, "SCRAPER_API_KEY", ""), \
                mock.patch("depop_client.requests.get", return_value=response) as mock_get, \
                mock.patch("depop_client._extract_product_objects", return_value=[]) as mock_extract:
            listings = depop_client.fetch_listings("q")

        self.assertEqual(listings, [])
        mock_get.assert_called_once()
        mock_extract.assert_called_once_with("<html>direct</html>")


class TestMaxDetailFetchesCap(unittest.TestCase):
    def test_more_survivors_than_cap_only_fetches_cap_many_and_warns(self):
        cards = [_card(slug=f"slug-{i}") for i in range(5)]
        search_resp = _mock_response(200, {"products": cards, "meta": {}, "market": "us", "query": "q"})
        detail_responses = [_mock_response(200, _detail(slug=f"slug-{i}")) for i in range(5)]

        with mock.patch.object(config, "SCRAPER_API_KEY", "sb_live_test"), \
                mock.patch.object(config, "TARGET_SIZES", ["0"]), \
                mock.patch.object(config, "MAX_PRICE", 25.0), \
                mock.patch.object(config, "MAX_DETAIL_FETCHES_PER_RUN", 2), \
                mock.patch("depop_client.requests.get", side_effect=[search_resp] + detail_responses) as mock_get, \
                self.assertLogs("depop_client", level="WARNING") as log_ctx:
            listings = depop_client.fetch_listings("q")

        self.assertEqual(len(listings), 2)
        self.assertEqual(mock_get.call_count, 1 + 2)  # search + capped detail calls
        self.assertTrue(any("MAX_DETAIL_FETCHES_PER_RUN" in message for message in log_ctx.output))


if __name__ == "__main__":
    unittest.main()

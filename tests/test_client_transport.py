"""Unit tests for depop_client._fetch_search_html's transport selection
(direct request vs. Bright Data Web Unlocker). Run with:
python -m unittest tests.test_client_transport or: python tests/test_client_transport.py
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import depop_client


def _mock_response(status_code: int, text: str = ""):
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


class TestBrightDataTransport(unittest.TestCase):
    def test_posts_to_brightdata_with_expected_payload_and_returns_text(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "test-key"), \
                mock.patch.object(config, "SCRAPER_ZONE", "my_zone"), \
                mock.patch("depop_client.requests.post", return_value=_mock_response(200, "<html>ok</html>")) as mock_post:
            result = depop_client._fetch_search_html("lululemon speedup shorts")

        self.assertEqual(result, "<html>ok</html>")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.brightdata.com/request")

        payload = kwargs["json"]
        self.assertEqual(payload["zone"], "my_zone")
        self.assertEqual(payload["format"], "raw")
        self.assertIn("https://www.depop.com/search/?", payload["url"])
        self.assertIn("q=lululemon+speedup+shorts", payload["url"])
        self.assertIn("sort=newest", payload["url"])

        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_401_raises_value_error(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "test-key"), \
                mock.patch("depop_client.requests.post", return_value=_mock_response(401, "unauthorized")):
            with self.assertRaises(ValueError):
                depop_client._fetch_search_html("q")

    def test_403_raises_value_error(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "test-key"), \
                mock.patch("depop_client.requests.post", return_value=_mock_response(403, "forbidden")):
            with self.assertRaises(ValueError):
                depop_client._fetch_search_html("q")

    def test_500_returns_none(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", "test-key"), \
                mock.patch("depop_client.requests.post", return_value=_mock_response(500, "oops")):
            result = depop_client._fetch_search_html("q")
        self.assertIsNone(result)

    def test_empty_scraper_key_uses_direct_get(self):
        with mock.patch.object(config, "SCRAPER_API_KEY", ""), \
                mock.patch("depop_client.requests.get", return_value=_mock_response(200, "<html>direct</html>")) as mock_get, \
                mock.patch("depop_client.requests.post") as mock_post:
            result = depop_client._fetch_search_html("q")

        self.assertEqual(result, "<html>direct</html>")
        mock_get.assert_called_once()
        mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

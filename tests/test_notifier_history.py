"""Unit tests for notifier.py's alert history logging. Run with:
python -m unittest tests.test_notifier_history or: python tests/test_notifier_history.py
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import filters
import notifier

FAKE_LISTING = {
    "id": "test-123",
    "title": "Lululemon Speedup Shorts 4\" 🩳, like new",
    "price": 23.5,
    "currency": "USD",
    "size": "4",
    "url": "https://www.depop.com/products/example-listing/",
    "image_url": "https://example.com/image.jpg",
    "condition": "used_excellent",
}


def _mock_success_response():
    response = mock.Mock()
    response.raise_for_status = mock.Mock()
    return response


class TestNotifierHistory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.history_path = os.path.join(self.tmpdir.name, "alerts_history.jsonl")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_send_alert_appends_full_history_line(self):
        with mock.patch.object(config, "ALERTS_HISTORY_PATH", self.history_path), \
                mock.patch.object(config, "NTFY_TOPIC", "dummy-topic"), \
                mock.patch("notifier.requests.post", return_value=_mock_success_response()):
            result = notifier.send_alert(FAKE_LISTING)

        self.assertTrue(result)
        with open(self.history_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)

        record = json.loads(lines[0])
        self.assertIn("sent_at", record)
        self.assertEqual(record["id"], FAKE_LISTING["id"])
        self.assertEqual(record["title"], FAKE_LISTING["title"])
        self.assertEqual(record["price"], FAKE_LISTING["price"])
        self.assertEqual(record["currency"], FAKE_LISTING["currency"])
        self.assertEqual(record["size"], FAKE_LISTING["size"])
        self.assertEqual(record["url"], FAKE_LISTING["url"])
        self.assertEqual(record["image_url"], FAKE_LISTING["image_url"])
        self.assertEqual(record["condition_note"], filters.condition_note(FAKE_LISTING))

    def test_send_alert_body_ends_with_condition_note(self):
        with mock.patch.object(config, "ALERTS_HISTORY_PATH", self.history_path), \
                mock.patch.object(config, "NTFY_TOPIC", "dummy-topic"), \
                mock.patch("notifier.requests.post", return_value=_mock_success_response()) as mock_post:
            notifier.send_alert(FAKE_LISTING)

        posted_body = mock_post.call_args.kwargs["data"].decode("utf-8")
        last_line = posted_body.splitlines()[-1]
        self.assertEqual(last_line, filters.condition_note(FAKE_LISTING))
        self.assertEqual(last_line, '✓ Condition: says "like new"')

    def test_send_alert_still_returns_true_when_history_unwritable(self):
        unwritable_path = os.path.join(self.tmpdir.name, "no-such-dir", "alerts_history.jsonl")
        with mock.patch.object(config, "ALERTS_HISTORY_PATH", unwritable_path), \
                mock.patch.object(config, "NTFY_TOPIC", "dummy-topic"), \
                mock.patch("notifier.requests.post", return_value=_mock_success_response()):
            result = notifier.send_alert(FAKE_LISTING)

        self.assertTrue(result)
        self.assertFalse(os.path.exists(unwritable_path))


if __name__ == "__main__":
    unittest.main()

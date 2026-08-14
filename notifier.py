"""Sends ntfy.sh push notifications for matched Depop listings."""

import logging
import sys

import requests

import config

logger = logging.getLogger(__name__)

NTFY_BASE_URL = "https://ntfy.sh"
REQUEST_TIMEOUT_SECONDS = 10


def send_alert(listing: dict) -> bool:
    """POST a push notification for listing to ntfy.sh. Returns True on success.

    Raises if NTFY_TOPIC is unset (config/schema error, crash loudly). Network
    errors/timeouts are logged and return False so one failed push doesn't
    kill a run.
    """
    if not config.NTFY_TOPIC:
        raise ValueError("NTFY_TOPIC is not set, cannot send alert")

    body_lines = [
        listing["title"],
        f"{listing['price']} {listing['currency']}",
    ]
    if listing.get("size"):
        body_lines.append(f"Size: {listing['size']}")
    body = "\n".join(body_lines)

    # ntfy headers must be latin-1 safe (listing titles may contain emoji), so
    # arbitrary text stays in the body -- headers only carry ASCII-safe values.
    headers = {
        "Title": "New Depop match",
        "Priority": "high",
        "Tags": "shorts",
        "Click": listing["url"],
    }
    if listing.get("image_url"):
        headers["Attach"] = listing["image_url"]

    try:
        response = requests.post(
            f"{NTFY_BASE_URL}/{config.NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info("Alert sent for listing %s", listing.get("id"))
        return True
    except requests.RequestException as e:
        logger.error("Failed to send alert for listing %s: %s", listing.get("id"), e)
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)

    fake_listing = {
        "id": "test-123",
        "title": "Lululemon Speedup Shorts 4\" 🩳",
        "price": 25.0,
        "currency": "GBP",
        "size": "UK 8",
        "url": "https://www.depop.com/products/example-listing/",
        "image_url": "https://example.com/image.jpg",
    }

    print("Sending one test alert via ntfy.sh...")
    result = send_alert(fake_listing)
    print(f"Alert sent: {result}" if result else "Alert failed, check logs above.")

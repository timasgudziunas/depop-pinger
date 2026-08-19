"""Sends ntfy.sh push notifications for matched Depop listings."""

import json
import logging
import sys
from datetime import datetime, timezone

import requests

import config

logger = logging.getLogger(__name__)

NTFY_BASE_URL = "https://ntfy.sh"
REQUEST_TIMEOUT_SECONDS = 10

_CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


def _format_price(price: float, currency: str) -> str:
    """25.0/'USD' -> '$25', 23.5/'USD' -> '$23.50'. Currencies without a
    known symbol fall back to '25 XXX' so the amount is never ambiguous."""
    amount = f"{price:.2f}".removesuffix(".00")
    symbol = _CURRENCY_SYMBOLS.get(currency)
    return f"{symbol}{amount}" if symbol else f"{amount} {currency}"


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
        _format_price(listing["price"], listing["currency"]),
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
        logger.info(
            "Alert sent: id=%s title=%r price=%s size=%s url=%s",
            listing.get("id"),
            listing.get("title"),
            _format_price(listing["price"], listing["currency"]),
            listing.get("size"),
            listing.get("url"),
        )
        _append_history(listing)
        return True
    except requests.RequestException as e:
        logger.error("Failed to send alert for listing %s: %s", listing.get("id"), e)
        return False


def _append_history(listing: dict) -> None:
    """Append one JSON line recording this alert to
    config.ALERTS_HISTORY_PATH. Best-effort: the push already succeeded, so
    a failure to write history is logged and swallowed rather than making
    send_alert report failure."""
    record = {
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "id": listing.get("id"),
        "title": listing.get("title"),
        "price": listing.get("price"),
        "currency": listing.get("currency"),
        "size": listing.get("size"),
        "url": listing.get("url"),
        "image_url": listing.get("image_url"),
    }
    try:
        with open(config.ALERTS_HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("Failed to write alert history for listing %s: %s", listing.get("id"), exc)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO)

    # Mirrors what depop_client._normalize_product actually returns for a
    # US-region search: USD currency, plain size-chart size string (no "UK"
    # prefix). Price is deliberately non-whole to exercise the cents path.
    fake_listing = {
        "id": "test-123",
        "title": "Lululemon Speedup Shorts 4\" 🩳",
        "price": 23.5,
        "currency": "USD",
        "size": "4",
        "url": "https://www.depop.com/products/example-listing/",
        "image_url": "https://example.com/image.jpg",
    }

    print("Sending one test alert via ntfy.sh...")
    result = send_alert(fake_listing)
    print(f"Alert sent: {result}" if result else "Alert failed, check logs above.")

"""All tunable criteria for depop-pinger. Edit this file only — no magic
numbers elsewhere.

HOW TO SET THE REAL CRITERIA (once sizes are confirmed):
  1. TARGET_SIZES: list the exact size strings as Depop shows them on
     listings, e.g. ["UK 6", "UK 8"] or ["S", "M"] or ["US 4", "US 6"].
     Depop sellers write sizes inconsistently, so include every variant you
     care about. Matching is case-insensitive. While this list is empty,
     size filtering is SKIPPED and every listing passes (useful for testing).
  2. MAX_PRICE: a number like 40.0 to only alert on listings at or under
     that price (in the listing's currency, GBP/USD as returned by Depop).
     Leave as None for no price ceiling.
"""

import os

# What to search Depop for.
SEARCH_QUERY = "lululemon speedup shorts"

# TODO: fill in with Timas's gf — exact sizes, as strings (see doc above).
TARGET_SIZES: list[str] = []

# TODO: optional price ceiling, e.g. 40.0. None = no ceiling.
MAX_PRICE: float | None = None

# Informational when running on GitHub Actions cron (the real interval lives
# in .github/workflows/check_listings.yml). Used only if run as a local loop.
POLL_INTERVAL_SECONDS = 90

# Days to keep listing IDs in seen_listings.json before pruning.
SEEN_RETENTION_DAYS = 14

# ntfy.sh topic — set via environment (GitHub Actions secret / local .env).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

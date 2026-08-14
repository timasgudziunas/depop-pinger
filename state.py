"""Tracks which Depop listing IDs have already been alerted on.

Persists to seen_listings.json as {listing_id: first_seen_iso_timestamp}.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_listings.json")


def load_seen(path: str = DEFAULT_STATE_PATH) -> dict:
    """Load the seen-listings state file; missing file means first run (empty state)."""
    if not os.path.exists(path):
        logger.info("No state file at %s, starting with empty state", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        # Corrupt JSON crashes loudly here (schema error, per project convention).
        return json.load(f)


def is_new(listing_id: str, seen: dict) -> bool:
    """Return True if listing_id has not already been recorded as seen."""
    return listing_id not in seen


def mark_seen(listing_id: str, seen: dict) -> None:
    """Record listing_id as seen now (in-place), if not already present."""
    if listing_id not in seen:
        seen[listing_id] = datetime.now(timezone.utc).isoformat()


def save_seen(seen: dict, path: str = DEFAULT_STATE_PATH) -> None:
    """Prune entries older than config.SEEN_RETENTION_DAYS, then write to disk."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.SEEN_RETENTION_DAYS)
    pruned = {}
    for listing_id, timestamp_iso in seen.items():
        first_seen = datetime.fromisoformat(timestamp_iso)
        if first_seen >= cutoff:
            pruned[listing_id] = timestamp_iso
    removed = len(seen) - len(pruned)
    if removed:
        logger.info("Pruned %d entries older than %d days", removed, config.SEEN_RETENTION_DAYS)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pruned, f, indent=2)

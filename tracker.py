"""Orchestrates one check cycle: fetch -> filter -> dedupe -> notify -> save.

Run once per invocation (GitHub Actions cron calls this on a schedule).
Exits non-zero on unhandled errors so Actions surfaces failures.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config
import depop_client
import filters
import notifier
import state

# Scheduled-task runs are headless, so mirror everything to a local log
# file. force=True replaces the stdout-only config the imported modules
# already installed at import time.
_LOG_DIR = Path(__file__).with_name("data") / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            _LOG_DIR / "tracker.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        ),
    ],
    force=True,
)
logger = logging.getLogger(__name__)


def run_once() -> None:
    """Fetch current listings, alert on new matches, persist state."""
    listings = depop_client.fetch_listings(config.SEARCH_QUERY)
    matched = [listing for listing in listings if filters.matches_criteria(listing)]

    seen = state.load_seen()
    new_matches = [listing for listing in matched if state.is_new(listing["id"], seen)]

    if not seen and new_matches:
        # First run (no state yet): seed silently instead of blasting an alert
        # for every listing already live. Alerts start from the next run.
        logger.info("First run: seeding %d current matches without alerting", len(new_matches))
        for listing in new_matches:
            state.mark_seen(listing["id"], seen)
        state.save_seen(seen)
        return

    alerts_sent = 0
    for listing in new_matches:
        if notifier.send_alert(listing):
            alerts_sent += 1
        # Mark seen even if the push failed: a listing that failed to notify
        # once should not re-alert on every subsequent run.
        state.mark_seen(listing["id"], seen)

    state.save_seen(seen)
    logger.info(
        "Checked %d listings, %d matched criteria, %d new, %d alerts sent",
        len(listings),
        len(matched),
        len(new_matches),
        alerts_sent,
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run_once()

"""Orchestrates one check cycle: fetch -> filter -> dedupe -> notify -> save.

Run once per invocation (GitHub Actions cron calls this on a schedule).
Exits non-zero on unhandled errors so Actions surfaces failures.

seen_listings.json semantics (changed 2026-08-23, ScrapeBadger swap): a
listing id is marked seen as soon as it's EVALUATED (returned by
depop_client.fetch_listings at all), not only when it matches and gets
alerted on. This is what makes ScrapeBadger's per-listing detail fetch a
one-time cost per listing -- fetch_listings is passed skip_ids=set(seen) so
it never re-spends a detail call on an id already in state, matching or not.
Under the old Bright Data transport, "seen" meant "already alerted" only,
because that transport had no separate per-listing fetch to economize on.

Note: seen_listings.json already holds numeric Depop ids from the old
transport (pre-2026-08-23), while ScrapeBadger keys new entries on slugs
(strings) instead -- see depop_client.py. The two id shapes simply coexist
in the same dict; old numeric-id entries age out via the normal
config.SEEN_RETENTION_DAYS pruning in state.save_seen, nothing was migrated.
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
    """Fetch listings not yet evaluated, alert on ones matching criteria,
    mark every listing returned this run as seen (see module docstring:
    "seen" now means "evaluated", not just "alerted on"). State is loaded
    FIRST so its ids can be passed as fetch_listings' skip_ids -- that's what
    lets ScrapeBadger detail lookups be a one-time cost per listing."""
    seen = state.load_seen()
    listings = depop_client.fetch_listings(config.SEARCH_QUERY, skip_ids=set(seen))
    # fetch_listings already excluded anything in `seen` via skip_ids, so
    # everything returned here is inherently new -- "new_matches" is simply
    # the subset that also matches criteria.
    matched = [listing for listing in listings if filters.matches_criteria(listing)]
    new_matches = matched

    if not seen and new_matches:
        # First run (no state yet): seed silently instead of blasting an alert
        # for every listing already live. Alerts start from the next run.
        # Seed EVERY fetched listing (not just matches) so the "evaluated"
        # baseline is established consistently with later runs.
        logger.info("First run: seeding %d current matches without alerting", len(new_matches))
        for listing in listings:
            state.mark_seen(listing["id"], seen)
        state.save_seen(seen)
        return

    alerts_sent = 0
    for listing in new_matches:
        if notifier.send_alert(listing):
            alerts_sent += 1

    # Mark EVERY returned listing seen, not just matches: a non-matching
    # listing has still been fully evaluated (ScrapeBadger detail fetch
    # spent, if applicable), so re-fetching its detail next run would waste
    # a call for no new information.
    for listing in listings:
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

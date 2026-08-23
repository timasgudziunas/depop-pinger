"""All tunable criteria for depop-pinger. Edit this file only — no magic
numbers elsewhere.

Filter model (see filters.py): every criterion below is checked
independently, and a listing must pass ALL of them to trigger an alert. Any
criterion whose config value is empty/None is SKIPPED entirely (every
listing passes that check) — useful for loosening the filter temporarily
without touching filters.py. Text matching (keywords, exclusions) is
case-insensitive and normalizes hyphens to spaces first, so "speed-up" and
"speed up" are treated the same.

Real criteria filled in from CRITERIA.md, 2026-08-17; sizes revised to
0-only per the expert, 2026-08-23.
"""

import os
from pathlib import Path

# Local runs (Task Scheduler fires tracker.py with no shell profile) get
# their env vars from the gitignored .env file next to this module; GitHub
# Actions injects secrets directly. Already-set environment always wins.
_env_file = Path(__file__).with_name(".env")
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _value = _line.partition("=")
            os.environ.setdefault(_key.strip(), _value.strip())

# What to search Depop for.
SEARCH_QUERY = "lululemon speedup shorts"

# Listing text must contain at least one of these (case-insensitive substring,
# after hyphens are normalized to spaces). "speedup"/"speed up" also cover the
# variants sellers use: "speed ups", "speedups", "speed up short",
# "lulu speed up", "lululemon speedups", "lululemon speed ups", "speed-up".
REQUIRED_KEYWORDS: list[str] = ["speed up", "speedup"]

# Instant disqualifiers, matched case-insensitively on whole words/phrases
# (word-boundary regex, hyphens normalized to spaces, curly quotes to straight).
# NOTE: matched against the listing text sellers type, so keep terms specific.
EXCLUDED_TERMS: list[str] = [
    # dupes / wrong product
    "dupe", "dupes", "inspired", "similar to", "style", "rep", "lookalike", "kids",
    # wrong inseam (only 2.5 inch wanted; 4 and 6 inch versions exist).
    # Bare "4"/"6" are NOT excluded -- they'd collide with size 4/6 mentions.
    '4"', "4 inch", "4inch", "4in", '6"', "6 inch", "6inch", "6in",
    # wrong rise (low rise only)
    "mid rise", "high rise", "high waist", "high waisted",
    # liner cut out = instant skip
    "liner removed", "lining removed", "liner cut", "lining cut", "no liner", "no lining",
    # condition dealbreakers
    "stain", "stains", "stained", "pilling", "altered", "hemmed",
    "smoke home", "smoking home", "smoker", "pet hair",
]

# Exact size strings to alert on (case-insensitive equality against the
# listing's size field). Size 0 ONLY as of 2026-08-23 (expert revision in
# CRITERIA.md Q7); XXS kept as the letter form of 0.
TARGET_SIZES: list[str] = ["0", "XXS", "US 0"]

# Hard price cap in the listing's currency (item price as Depop displays it,
# excluding shipping). At-or-under pings, over stays silent.
MAX_PRICE: float | None = 25.0

# Depop condition enum values that are acceptable (minimum: excellent used).
# A listing with no condition field passes (text dealbreakers still apply).
ALLOWED_CONDITIONS: list[str] = ["brand_new", "used_like_new", "used_excellent"]

# Seller countries to alert on. A listing with no country field passes.
ALLOWED_COUNTRIES: list[str] = ["US", "CA"]

# Informational only: the real cadence lives in
# .github/workflows/check_listings.yml (cron, every 10 min as of
# 2026-08-19). Used only if tracker.py is ever run as a manual local loop.
POLL_INTERVAL_SECONDS = 90

# Days to keep listing IDs in seen_listings.json before pruning.
SEEN_RETENTION_DAYS = 14

# ntfy.sh topic — set via environment (GitHub Actions secret / local .env).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# ScrapeBadger API key (sb_live_... prefix) for their dedicated Depop API,
# live as of 2026-08-23, replacing Bright Data Web Unlocker. Pay-as-you-go
# $0.15 per 1,000 credits; both a search call and a detail call cost 10
# credits each (failed requests are free). Free tier rate limit: 5
# requests/minute. Empty = fetch depop.com directly (works on residential
# IPs only; datacenter IPs are Cloudflare-blocked).
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")

# Depop market/region to search via ScrapeBadger. Supported codes (per
# ScrapeBadger): us, gb, au, ie, it, fr, de, es, nl, nz. Canada isn't a
# selectable market -- CA-seller country filtering (config.ALLOWED_COUNTRIES
# includes "CA") is effectively delegated to whatever CA listings surface
# under the "us" market, since ScrapeBadger doesn't expose seller country at
# all (see depop_client.py's ScrapeBadger normalization -- country is
# always None).
MARKET = "us"

# Cost/rate-limit bound on ScrapeBadger detail lookups (10 credits each,
# free tier 5 requests/minute) per tracker run. Cards are cheaply
# prefiltered first (see depop_client.py), so this caps only the surviving,
# plausibly-matching candidates -- if it binds, dropped cards are simply
# reconsidered next run (they aren't marked seen without a detail fetch). A
# full cap of 8 costs at most ~2 minutes of 429 backoff worst-case at 5
# req/min.
MAX_DETAIL_FETCHES_PER_RUN = 8

# Where full alert content is appended (one JSON object per line) so past
# pings can be reviewed later. Tracked in git; the Actions cron commits it
# back after each run that alerts.
ALERTS_HISTORY_PATH = Path(__file__).with_name("alerts_history.jsonl")

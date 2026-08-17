"""All tunable criteria for depop-pinger. Edit this file only — no magic
numbers elsewhere.

Filter model (see filters.py): every criterion below is checked
independently, and a listing must pass ALL of them to trigger an alert. Any
criterion whose config value is empty/None is SKIPPED entirely (every
listing passes that check) — useful for loosening the filter temporarily
without touching filters.py. Text matching (keywords, exclusions) is
case-insensitive and normalizes hyphens to spaces first, so "speed-up" and
"speed up" are treated the same.

Real criteria filled in from CRITERIA.md, 2026-08-17.
"""

import os

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
# listing's size field). Speed Ups in 0 / 2 / XXS / XS.
TARGET_SIZES: list[str] = ["0", "2", "XS", "XXS", "US 0", "US 2"]

# Hard price cap in the listing's currency (item price as Depop displays it,
# excluding shipping). At-or-under pings, over stays silent.
MAX_PRICE: float | None = 25.0

# Depop condition enum values that are acceptable (minimum: excellent used).
# A listing with no condition field passes (text dealbreakers still apply).
ALLOWED_CONDITIONS: list[str] = ["brand_new", "used_like_new", "used_excellent"]

# Seller countries to alert on. A listing with no country field passes.
ALLOWED_COUNTRIES: list[str] = ["US", "CA"]

# Informational when running on GitHub Actions cron (the real interval lives
# in .github/workflows/check_listings.yml). Used only if run as a local loop.
POLL_INTERVAL_SECONDS = 90

# Days to keep listing IDs in seen_listings.json before pruning.
SEEN_RETENTION_DAYS = 14

# ntfy.sh topic — set via environment (GitHub Actions secret / local .env).
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

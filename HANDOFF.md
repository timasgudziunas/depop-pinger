# HANDOFF.md — Session Handoff (updated 2026-08-17 ~14:45 UTC, supersedes all 2026-08-15 and earlier versions)

> For a fresh Claude session with no memory of prior conversations: read
> this file first, then the repo CLAUDE.md for hard constraints (no
> auto-buy, no Cloudflare evasion), then `depop_client.py`'s module
> docstring if touching the data source. `CRITERIA.md` holds the expert's
> filled-in answers that the live config was built from.

## Current state (as of 2026-08-17 ~14:45 UTC)

**The pinger is DONE and LIVE.** All 8 PLAN.md phases complete. Real
criteria from CRITERIA.md are in `config.py`, filters implemented and
tested (52/52 unit tests passing), GitHub Actions cron active with the
`NTFY_TOPIC` secret set (added 2026-08-17 14:16 UTC), manual dispatch run
green (14:17 UTC), scheduled runs green all day. Actual cron cadence
observed: every 25-60 min despite the `*/5` schedule (GitHub throttling,
known limitation).

Live criteria (from CRITERIA.md, translated 2026-08-17): Speed Up model
only ("speed up"/"speedup" required in text), sizes 0/2/XS/XXS, price cap
$25.00 (item price excl. shipping, listing currency), condition
brand_new/used_like_new/used_excellent (structured Depop enum, `used_good`
and `used_fair` rejected), sellers US+CA, kids items excluded, wrong
inseam (4"/6") and mid/high rise and liner-removed and dealbreaker terms
(stains/pilling/altered/hemmed/smoke/pet hair/dupe words) excluded via
word-boundary text matching. No color filter by choice (option a: judge
from photo). All knobs in `config.py`; empty list/None disables a check.

Live verification 2026-08-17 ~14:32 UTC: 24 real listings fetched, 3
passed all criteria ($17 size 0, $17 size 2, $13 size 2, all like-new US),
every skip traced to a correct criterion. Read-only check; no state
mutated, no pings sent.

Notification format (fixed 2026-08-15): price renders as `$25` / `$23.50`
(`£` for GBP, `30 CAD` fallback); size shown verbatim as Depop reports it
(plain "4"-style for US listings — a "UK 8"-style size is deliberately NOT
stripped since UK 8 ≠ Lululemon 8).

## Just completed (this session)

- Translated CRITERIA.md answers into `config.py` constants + new filter
  logic in `filters.py` (keywords, exclusions, condition, country, kids —
  condition/country/is_kids come from structured payload fields newly
  extracted in `depop_client._normalize_product`).
- Tests grown 19 → 52 (incl. new `tests/test_client_fixture.py`; exactly
  2 of the 24 fixture listings pass the real config — asserted by id).
- Owner completed all TODO.md steps (ntfy subscribed, test push received,
  secret set, manual run green); TODO.md deleted as fully spent.
- Live read-only filter check against real Depop (see above).

## In progress / where it stopped

Nothing in progress. First alerts under real criteria will come from the
cron; up to 3 pings possible on the first run after this push if the 3
currently-live matches weren't in the seeded state (couldn't verify:
local IP started getting Cloudflare 403s after ~4 rapid requests, and the
repo rule is to back off, not retry through it. Actions IPs unaffected).

## Next steps, in priority order

1. **Watch the first days of alerts** (owner). Tune in `config.py` only:
   spammy → add EXCLUDED_TERMS / tighten; missing good listings → the
   most likely culprits are `"style"` in EXCLUDED_TERMS (expert-requested
   but broad: kills "90s style" etc.) and `"4in"` (can't distinguish
   "4 inch inseam" from "worn 4 in a row"), or the strict condition list.
2. **Optional (PLAN.md Phase 8 leftover):** widen `SEARCH_QUERY` if early
   runs show Depop's search itself missing listings (the required-keyword
   filter makes a broader query safe).
3. If cron cadence (25-60 min real) proves too slow for items that sell in
   minutes: local always-on loop via Task Scheduler
   (`POLL_INTERVAL_SECONDS=90` already in config; skill
   `register-windows-scheduled-task`).

## Settled questions (do not re-litigate)

- Data source = Depop's own search-page RSC payload (option 1). Old JSON
  API is dead (HTTP 410, verified 2026-08-14). Details in
  `depop_client.py` docstring.
- Condition filtering uses the structured `attributes.condition` enum
  (brand_new/used_like_new/used_excellent/used_good/used_fair observed),
  NOT text parsing. Missing condition/country passes by design (filter on
  positive evidence only).
- Bare "4"/"6" are NOT excluded terms (they collide with size mentions);
  only inch-marked forms. Settled during translation, don't "fix" it.
- Notification size is shown verbatim, never UK-stripped (UK 8 = US 4).

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL live criteria knobs (sizes, cap, keywords, exclusions, conditions, countries) |
| `filters.py` | pure matching logic incl. `_normalize_text` (casefold, curly quotes, hyphens) |
| `depop_client.py` | data source + schema docs; only file to touch if Depop changes |
| `CRITERIA.md` | expert's filled answers — authoritative spec behind config.py |
| `seen_listings.json` | dedupe state, committed back by each Actions run |
| `tests/` | 52 tests; `test_client_fixture.py` pins real-config behavior to the fixture |
| `.github/workflows/check_listings.yml` | */5 cron (real cadence 25-60 min) |

## Operational landmines

1. Local IP gets Cloudflare 403s after a burst of requests (~4 in a
   minute, observed 2026-08-17); single retry usually clears one, but back
   off instead of hammering. GitHub Actions runners were never blocked.
2. GitHub Actions cron disables after 60 days of repo inactivity.
3. The Action commits `seen_listings.json` back to main — always
   `git pull --rebase` before pushing local work.
4. Schema errors from the client = Depop changed their frontend; fix
   `depop_client.py` only, or swap to a scraper API (CLAUDE.md option 2).
5. Reconfigure stdout to UTF-8 in any new CLI entry point (emoji in
   listing text crashes bare prints on Windows).
6. Never set ANTHROPIC_API_KEY in this repo's automations (Max-plan rule).

## Quick health check

```powershell
gh run list --workflow=check_listings.yml --limit 3
python -m unittest discover tests
python depop_client.py
```
Healthy ≈ recent runs "completed success", 52 tests OK, client prints ~24
live listings (a lone 403 warning is fine; persistent 403s are landmine 1).

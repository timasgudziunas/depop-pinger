# HANDOFF.md

Authoritative current state. Read this first; refresh at session end.

## Current state (as of 2026-08-14 ~11:15 ET)

Phases 0 through 6 complete and committed; Phase 7 half done. All code is
built, unit tested (19/19 passing), and verified against live Depop:
`python depop_client.py` returned 24 real listings for "lululemon speedup
shorts" and `python tracker.py` did its first-run silent seed into
`seen_listings.json` (24 IDs). Everything is pushed to
github.com/timasgudziunas/depop-pinger, so the */5-minute cron workflow is
ACTIVE but cannot alert yet (no NTFY_TOPIC secret on the repo).

Data source note: Depop's old `webapi.depop.com` JSON endpoint is dead
(HTTP 410). `depop_client.py` fetches depop.com's own search-page HTML and
parses the embedded Next.js RSC payload. Schema details, size/price field
mapping, and the `sort=newest` best-effort caveat are all in that module's
docstring. No Cloudflare challenges seen across ~30 dev requests.

## What's blocked and on whom

All remaining work needs Timas, in this order:

1. Subscribe to the ntfy topic in the ntfy app on his phone. The topic
   value is in the local gitignored `.env` (treated as a secret, not
   written in repo docs).
2. Run `python notifier.py` locally, confirm the test push lands on the
   phone (Phase 5 last checkbox).
3. `gh auth login`, then `gh secret set NTFY_TOPIC` with that same value
   (or add it via GitHub web UI: repo Settings > Secrets and variables >
   Actions). Until this exists, any cron run that finds a new listing will
   FAIL loudly (ValueError on missing NTFY_TOPIC) rather than alert.
4. Trigger one manual workflow run (`gh workflow run check_listings.yml`
   or the Actions tab) and confirm green (Phase 7 last checkbox).
5. Fill in `TARGET_SIZES` / `MAX_PRICE` in config.py with the real sizes
   from his girlfriend (Phase 8). Until then criteria are wide open:
   every listing for the query matches (fine for testing, spammy for real
   use). Depop sizes for these listings come through as plain numbers like
   "2", "4", "6".

## Standing cautions

- GitHub Actions cron disables after 60 days of repo inactivity.
- Real cron cadence is */5 nominal but often 3-15 min delayed on GitHub's
  runners; if that proves too slow for items that sell in minutes, the
  fallback is a local always-on loop via Task Scheduler (POLL_INTERVAL_
  SECONDS in config.py already exists for that).
- If the client starts returning schema errors, Depop changed their
  frontend payload; fix `depop_client.py` only (see its docstring), or
  fall back to a scraper API per CLAUDE.md option 2.

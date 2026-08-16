# HANDOFF.md

Authoritative current state. Read this first; refresh at session end.

## Current state (as of 2026-08-15)

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

## Next steps, in order

1. **Timas works through `TODO.md`** (subscribe to the ntfy topic from the
   local gitignored `.env`, confirm `python notifier.py` lands a push on
   the phone, `gh auth login` + set the `NTFY_TOPIC` repo secret, trigger
   one manual workflow run). Ticks the last Phase 5 and Phase 7 boxes in
   PLAN.md when done. Until the secret exists, any cron run that finds a
   new listing FAILS loudly (red X) rather than alerting.
2. **Timas sends `CRITERIA.md` to the expert (girlfriend)** and gets it
   back with the answers filled in under each question. That completed
   document is the authoritative spec for what to target.
3. **Next Claude session translates the completed CRITERIA.md into code**
   (this replaces the old bare "fill in TARGET_SIZES/MAX_PRICE" Phase 8):
   - Sizes and max price map directly onto `TARGET_SIZES` / `MAX_PRICE`
     in config.py (sizes come through as plain numbers like "2", "4").
   - IMPORTANT for that session: several CRITERIA.md answers go beyond
     what filters.py currently supports (it only does size + price).
     Keyword include/exclude lists (Q1-3, dupes/other models), inseam and
     rise (Q4-5), color (Q12), condition/liner dealbreakers (Q13-15), and
     US-only (Q16) all need NEW filter logic on the listing description
     text, plus possibly widening/adding search queries in config.py.
     Scope that as a Phase 9 in PLAN.md before coding it, keep new
     criteria as config.py constants, unit test against the fixture.
4. **Go live and tune**: commit the criteria, watch the first days of
   alerts, tighten keywords if pings are spammy or widen if listings are
   being missed (the alert-vs-miss tradeoff choices are in CRITERIA.md
   answers, e.g. Q8 unknown sizes, Q12 color option a/b).

Until criteria are in, config is wide open: every listing for the query
matches (fine for testing, spammy for real use).

## Standing cautions

- GitHub Actions cron disables after 60 days of repo inactivity.
- Real cron cadence is */5 nominal but often 3-15 min delayed on GitHub's
  runners; if that proves too slow for items that sell in minutes, the
  fallback is a local always-on loop via Task Scheduler (POLL_INTERVAL_
  SECONDS in config.py already exists for that).
- If the client starts returning schema errors, Depop changed their
  frontend payload; fix `depop_client.py` only (see its docstring), or
  fall back to a scraper API per CLAUDE.md option 2.

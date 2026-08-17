# PLAN.md

Phased build plan for depop-pinger. Work through phases in order — each one
should leave the repo in a working, testable state before moving to the next.

## Phase 0 — Repo setup

- [x] Create repo `depop-pinger` (private or public — public is fine/free
      for GitHub Actions, same as ticket-sniper, but keep any API keys out
      of it regardless).
- [x] `requirements.txt`: `requests` (add more only if the chosen data
      source needs a specific client library).
- [x] `.env.example` documenting expected environment variables:
      `NTFY_TOPIC`, and `SCRAPER_API_KEY` if Phase 2 goes with option 2.
- [x] `.gitignore`: `.env`, `__pycache__/`.

## Phase 1 — config.py

- [x] Define constants:
  - `SEARCH_QUERY = "lululemon speedup shorts"`
  - `TARGET_SIZES = []` — **placeholder, to be filled in after Timas talks
    to his girlfriend about exact sizes**
  - `MAX_PRICE = None` — **placeholder, optional price ceiling**
  - `POLL_INTERVAL_SECONDS = 90` (informational only if running on GitHub
    Actions cron — cron interval is set in the workflow file instead)
  - `NTFY_TOPIC` read from environment
- [x] Add a comment block explaining exactly how to fill in `TARGET_SIZES`
      and `MAX_PRICE` once confirmed, so this file is self-documenting for
      non-technical edits later (his girlfriend may want to tweak criteria
      herself).

## Phase 2 — depop_client.py (data source)

- [x] Decide between the two data source options in CLAUDE.md. Start with
      option 1 (mimicked search request) for zero external dependencies.
      *(Went with option 1, but the old `webapi.depop.com` JSON endpoint is
      deprecated (HTTP 410) — the client fetches depop.com's own search
      results HTML and parses the embedded Next.js RSC payload instead.
      See depop_client.py module docstring for schema details and caveats.)*
- [x] Implement `fetch_listings(query: str) -> list[dict]` returning
      normalized dicts: `{id, title, price, size, url, image_url}`.
      *(Plus `currency`. `sort=newest` is best-effort — no timestamp field
      exists in the response to verify strict ordering.)*
- [x] Save a sample raw response as a fixture file for testing.
- [x] Manual smoke test: run standalone, confirm it returns real, current
      listings for "lululemon speedup shorts" with no crash. *(24 live
      listings returned, 2026-08-14.)*
- [x] If option 1 gets blocked/empty/inconsistent during smoke testing,
      swap to option 2 (scraper API) — only this file should need to change.
      *(Not needed — option 1 worked with no Cloudflare challenges.)*

## Phase 3 — filters.py

- [x] `matches_criteria(listing: dict, config) -> bool`:
      checks size against `TARGET_SIZES` (skip size filtering entirely if
      the list is still empty, so the tool is testable before criteria are
      finalized) and price against `MAX_PRICE` if set. *(Criteria injectable
      as kwargs for testing; listings with no parseable size do NOT match
      once sizes are specified — flip in filters.py if that under-fires.)*
- [x] Unit-test against the Phase 2 fixture with a few hand-picked
      pass/fail cases. *(tests/test_filters.py, 11 cases, all passing.)*

## Phase 4 — state.py

- [x] Load/save `seen_listings.json` as `{listing_id: first_seen_timestamp}`.
- [x] `is_new(listing_id) -> bool` and `mark_seen(listing_id)`.
- [x] Prune entries older than 14 days on each save. *(tests/test_state.py,
      8 cases, all passing.)*

## Phase 5 — notifier.py

- [x] `send_alert(listing: dict)` posts to ntfy.sh topic (`NTFY_TOPIC` env
      var) with title, price, size, and link — mirror the notifier pattern
      from ticket-sniper. *(Click header opens the listing; Attach header
      shows the item photo.)*
- [x] Manual test: trigger one fake alert, confirm it lands on phone.

## Phase 6 — tracker.py (orchestration)

- [x] `fetch_listings()` → `matches_criteria()` filter → `is_new()` filter →
      `send_alert()` for each new match → `mark_seen()` → save state.
      *(Plus: very first run (no state file) seeds all current matches
      silently instead of blasting an alert for every listing already live;
      failed pushes still mark seen so they don't re-alert every run.)*
- [x] Log a one-line summary each run (checked N listings, M matched
      criteria, K were new).
- [x] Exit cleanly with non-zero status on unhandled errors so GitHub
      Actions surfaces failures. *(End-to-end tested live 2026-08-14:
      24 listings fetched, first-run seed wrote seen_listings.json.)*

## Phase 7 — GitHub Actions

*(RETIRED 2026-08-17: GitHub runner IPs are Cloudflare-blocked by
depop.com — every cron run got HTTP 403 and fetched nothing. Hosting
moved to a local Task Scheduler task (`setup_task.ps1`, every 2 min);
the workflow remains as a manual dispatch probe. See HANDOFF.md.)*

- [x] `.github/workflows/check_listings.yml`: cron schedule (every 5–15 min
      — same constraint as ticket-sniper: 5 min is GitHub's minimum, 15 min
      is the friendlier default for a public repo), checkout, set up
      Python, install deps, run `tracker.py` with secrets injected, commit
      updated `seen_listings.json` back to the repo. *(Went with */5 since
      listings sell within minutes; relax to */15 if runs pile up.)*
- [x] Add `NTFY_TOPIC` (and `SCRAPER_API_KEY` if applicable) as GitHub
      Actions repo secrets.
- [x] Trigger a manual workflow run to confirm end-to-end before relying on
      the schedule.

## Phase 8 — Fill in real criteria and go live

- [x] Once Timas has the exact sizes (and optional price ceiling) from his
      girlfriend, fill in `TARGET_SIZES` / `MAX_PRICE` in `config.py`,
      commit, and let the schedule run for real. *(Real criteria from
      CRITERIA.md, filled in 2026-08-17: TARGET_SIZES 0/2/XS/XXS,
      MAX_PRICE 25.0, plus new REQUIRED_KEYWORDS / EXCLUDED_TERMS /
      ALLOWED_CONDITIONS / ALLOWED_COUNTRIES filters added to config.py and
      filters.py — see filters.py for the full check list.)*
- [ ] Optional follow-up: expand `SEARCH_QUERY` to catch listing title
      variants (e.g. "lulu speedup", "align speed up") if early runs show
      missed matches.

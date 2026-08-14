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

- [ ] Decide between the two data source options in CLAUDE.md. Start with
      option 1 (mimicked search request) for zero external dependencies.
- [ ] Implement `fetch_listings(query: str) -> list[dict]` returning
      normalized dicts: `{id, title, price, size, url, image_url}`.
- [ ] Save a sample raw response as a fixture file for testing.
- [ ] Manual smoke test: run standalone, confirm it returns real, current
      listings for "lululemon speedup shorts" with no crash.
- [ ] If option 1 gets blocked/empty/inconsistent during smoke testing,
      swap to option 2 (scraper API) — only this file should need to change.

## Phase 3 — filters.py

- [ ] `matches_criteria(listing: dict, config) -> bool`:
      checks size against `TARGET_SIZES` (skip size filtering entirely if
      the list is still empty, so the tool is testable before criteria are
      finalized) and price against `MAX_PRICE` if set.
- [ ] Unit-test against the Phase 2 fixture with a few hand-picked
      pass/fail cases.

## Phase 4 — state.py

- [ ] Load/save `seen_listings.json` as `{listing_id: first_seen_timestamp}`.
- [ ] `is_new(listing_id) -> bool` and `mark_seen(listing_id)`.
- [ ] Prune entries older than 14 days on each save.

## Phase 5 — notifier.py

- [ ] `send_alert(listing: dict)` posts to ntfy.sh topic (`NTFY_TOPIC` env
      var) with title, price, size, and link — mirror the notifier pattern
      from ticket-sniper.
- [ ] Manual test: trigger one fake alert, confirm it lands on phone.

## Phase 6 — tracker.py (orchestration)

- [ ] `fetch_listings()` → `matches_criteria()` filter → `is_new()` filter →
      `send_alert()` for each new match → `mark_seen()` → save state.
- [ ] Log a one-line summary each run (checked N listings, M matched
      criteria, K were new).
- [ ] Exit cleanly with non-zero status on unhandled errors so GitHub
      Actions surfaces failures.

## Phase 7 — GitHub Actions

- [ ] `.github/workflows/check_listings.yml`: cron schedule (every 5–15 min
      — same constraint as ticket-sniper: 5 min is GitHub's minimum, 15 min
      is the friendlier default for a public repo), checkout, set up
      Python, install deps, run `tracker.py` with secrets injected, commit
      updated `seen_listings.json` back to the repo.
- [ ] Add `NTFY_TOPIC` (and `SCRAPER_API_KEY` if applicable) as GitHub
      Actions repo secrets.
- [ ] Trigger a manual workflow run to confirm end-to-end before relying on
      the schedule.

## Phase 8 — Fill in real criteria and go live

- [ ] Once Timas has the exact sizes (and optional price ceiling) from his
      girlfriend, fill in `TARGET_SIZES` / `MAX_PRICE` in `config.py`,
      commit, and let the schedule run for real.
- [ ] Optional follow-up: expand `SEARCH_QUERY` to catch listing title
      variants (e.g. "lulu speedup", "align speed up") if early runs show
      missed matches.

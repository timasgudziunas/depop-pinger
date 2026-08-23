# HANDOFF.md — Session Handoff (updated 2026-08-23 ~20:15 UTC, supersedes all 2026-08-19 and earlier versions)

> For a fresh Claude session with no memory of prior conversations: read
> this file first, then the repo CLAUDE.md for hard constraints (no
> auto-buy, no Cloudflare evasion) and its "Data source options" section
> (ScrapeBadger Depop API as of 2026-08-23), then `depop_client.py`'s
> module docstring if touching the data source. `CRITERIA.md` holds the
> expert's answers behind config.py (revised 2026-08-23: size 0 only).

## Current state (as of 2026-08-23 ~20:15 UTC)

**LIVE and verified end to end on ScrapeBadger.** GitHub Actions cron
(`*/10`) runs `tracker.py`, which fetches through ScrapeBadger's Depop
API (two-step: search cards → prefilter → detail only for new
candidates). First verified-green cloud run: workflow run 32662828606,
2026-08-23 19:56 UTC, log shows "24 cards returned, 0 survived
prefilter" — the healthy signature (see landmine 2). Local manual run
identical. 71 unit tests green. Criteria: size 0 only (`TARGET_SIZES =
["0", "XXS", "US 0"]`), max $25, everything else per CRITERIA.md.

**Money state:** ScrapeBadger trial had 1,000 free credits; roughly 850
remain (estimate — ~15 searches and 1 detail spent on probes, local
runs, and task firings; exact number on their dashboard). At 10
credits/search and the `*/10` cron (~6 searches/hour), trial credits
last ~14 more hours from the timestamp above. **The $10 minimum top-up
buys ~66,000 credits ≈ 6+ weeks of runtime**; steady-state cost is
~$6.70/month, inside the owner's approved $10/month budget.

**Local Task Scheduler task `\DepopPinger\Check Listings` (2-min) is
still ENABLED but neutered:** its `SCRAPER_API_KEY` line in `.env` is
commented out (2026-08-23) because at 2-min cadence it was burning ~300
credits/hour. It currently falls back to free direct fetches. Disabling
it needs an elevated shell; the attempt this session got UAC-declined.

## Just completed (this session, 2026-08-23)

- Criteria revised to size 0 only per the expert (CRITERIA.md Q7,
  config.py, fixture tests restructured).
- Bright Data purchased, tested live, and found DEAD for this project:
  compliance-blocks depop.com (`policy_20050` via x-brd headers on an
  empty HTTP 200), KYC unblock is business-only. Full writeup in
  CLAUDE.md "Data source options". Client now raises clearly on that
  header pattern. Owner should request a refund of any Bright Data
  deposit.
- Transport swapped to ScrapeBadger Depop API (search+detail two-step,
  free-card prefilter, `MAX_DETAIL_FETCHES_PER_RUN` cap, 429 backoff via
  `reset_at`). Live-probed quirks are commented in code: sort value is
  `newest` (docs' `newlyListed` 502s); condition is schema.org-style
  (`UsedCondition`/`NewCondition`) so used-grade granularity is lost —
  generic used passes the condition gate, text dealbreakers + photos
  cover it.
- `seen_listings.json` semantics changed to "already EVALUATED" (not
  just alerted) so each listing costs at most one detail call ever;
  slugs are the new ids, old numeric ids age out via pruning.
- Real API fixtures captured (`tests/fixtures/scrapebadger_*.json`);
  suite 61 → 71 tests.
- Committed and pushed (`3d3e594`), workflow dispatched, first green run
  verified with state-commit-back machinery intact.

## In progress / where it stopped

Nothing half-built. Remaining items are owner actions (below) plus
watching the cron. The 19:54 UTC scheduled run failed (old code + new
key — transitional, expected); everything from 19:56 UTC on should be
green.

## Next steps, in priority order

1. **Owner: top up $10 at ScrapeBadger** (PAYG, card or crypto, credits
   never expire) BEFORE trial credits run out (~14h from timestamp
   above). When they run out, runs go red on search failures until the
   top-up — annoying but loud, not silent.
2. **Owner: disable the local task** from an elevated PowerShell:
   `Disable-ScheduledTask -TaskPath '\DepopPinger\' -TaskName 'Check Listings'`
   It's harmless but pointless while keyless (direct fetches mostly
   403), and a residential-IP success could double-alert vs Actions.
3. **After the task is disabled: uncomment `SCRAPER_API_KEY` in `.env`**
   (the line carries a comment saying exactly this) so manual local runs
   work again. Do NOT uncomment while the 2-min task is still enabled.
4. Watch a few cron firings (`gh run list`), then this repo is in
   steady state.

## Settled questions (do not re-litigate)

- **Bright Data is dead for depop.com** — compliance block verified live
  2026-08-23, KYC is business-only, personal accounts cannot pass. Treat
  as the standing result; do not retry it or suggest KYC.
- **Scraper = ScrapeBadger Depop API**, chosen 2026-08-23 under the
  owner's $10/month budget. ScraperAPI/ScrapingBee/ZenRows/ScrapFly all
  have $30-50 monthly minimums — out. Don't re-shop unless pricing or
  the API breaks.
- Hosting = GitHub Actions cron `*/10` (owner's call 2026-08-19,
  reaffirmed by the cost math: 4,464 searches/month ≈ $6.70). Local
  hosting is out (laptop sleep + 403s, documented 2026-08-19).
- Criteria are size 0 ONLY as of 2026-08-23 (expert revision). XXS kept
  as the letter form of 0 — flagged to owner, unobjected.
- Condition granularity loss (UsedCondition → passes) is accepted, per
  the owner's standing "ping and I judge from the photo" preference.
- Direct-fetch RSC path stays as the no-key fallback (residential IPs
  only); its parsing and fixtures are unchanged and still tested.

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL criteria knobs + .env loading + ScrapeBadger config (MARKET, MAX_DETAIL_FETCHES_PER_RUN) |
| `depop_client.py` | both transports: ScrapeBadger two-step (key set) and direct RSC (no key); the only file to touch if either changes |
| `tracker.py` | orchestration + the "seen = evaluated" semantics writeup |
| `notifier.py` | ntfy push + alert history append |
| `alerts_history.jsonl` | full content of every ping sent (tracked, committed back by Actions) |
| `seen_listings.json` | evaluated-listing state: slugs (new) + numeric ids (pre-2026-08-23, aging out) |
| `.github/workflows/check_listings.yml` | the scheduler: cron `*/10` + secret guard + commit-back |
| `setup_task.ps1` | local Task Scheduler registration — deprecated, task pending disable (Next steps 2) |
| `data\logs\tracker.log` | local runs' log (gitignored); Actions logs to the Actions console |
| `CRITERIA.md` | expert's answers — the spec behind config.py (Q7 revised 2026-08-23) |
| `tests/` | 71 tests; `test_scrapebadger_fixture.py` + `tests/fixtures/scrapebadger_*.json` are real captured responses |

## Operational landmines

1. Scheduled Actions runs are RED on purpose if `SCRAPER_API_KEY` is
   missing — that's the guard, not a bug. Same if ScrapeBadger credits
   run out: red runs near the top of the month-ish boundary = check the
   credit balance first.
2. **"0 listings returned" is NORMAL and healthy now** (prefilter
   discards non-size-0 cards before any spend). The health signal is the
   log line "N cards returned" with N > 0 (24 typical, never genuinely
   0 for this query — a 0-cards line logs as WARNING).
3. Free-tier rate limit is 5 requests/minute; the client sleeps and
   retries on 429 (`reset_at`-aware). A run with many new size-0
   listings can legitimately take a few minutes.
4. Do NOT uncomment `SCRAPER_API_KEY` in `.env` while the 2-min local
   task is still enabled — it burns ~300 credits/hour (~$32/month pace).
   Disable the task first (Next steps 2-3).
5. If the local task is ever recreated by hand it reverts to
   Interactive-only + battery-restricted — re-register via
   `setup_task.ps1` (elevated). (Moot once disabled.)
6. Schema errors from the client = Depop or ScrapeBadger changed shape;
   fix `depop_client.py` only. Search/detail/normalize are separate
   functions — check which layer broke first. Unknown condition strings
   log a WARNING and pass the filter — add them to `_CONDITION_MAP` once
   understood.
7. Reconfigure stdout to UTF-8 in any new CLI entry point (emoji in
   listing text crashes bare prints on Windows).
8. Never set ANTHROPIC_API_KEY in this repo's automations (Max-plan rule).
9. Notification size shown verbatim, never UK-stripped (UK 8 = US 4).
10. Bare "4"/"6" are NOT excluded terms (collide with size mentions);
    only inch-marked forms. Don't "fix" it.

## Quick health check

```powershell
gh run list --workflow=check_listings.yml --limit 5
gh run view --log $(gh run list --workflow=check_listings.yml --limit 1 --json databaseId --jq '.[0].databaseId') | Select-String "cards returned"
.venv\Scripts\python.exe -m unittest discover tests
```
Healthy ≈ recent runs green, latest log shows "24 cards returned, N
survived prefilter" (0 survivors is normal), 71 tests OK. Red runs +
"insufficient credits"-shaped errors = top up ScrapeBadger.

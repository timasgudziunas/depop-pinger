# HANDOFF.md — Session Handoff (updated 2026-08-19 ~16:55 UTC, supersedes all 2026-08-17 and earlier versions)

> For a fresh Claude session with no memory of prior conversations: read
> this file first, then the repo CLAUDE.md for hard constraints (no
> auto-buy, no Cloudflare evasion) and the Scheduling section (GitHub
> Actions cron via Bright Data, as of 2026-08-19), then
> `depop_client.py`'s module docstring if touching the data source.
> `CRITERIA.md` holds the expert's filled-in answers behind config.py.

## Current state (as of 2026-08-19 ~16:55 UTC)

**Hosting is moving BACK to GitHub Actions cron, blocked on one owner
step: the Bright Data API token.** Code is done, tested (59/59 unit
tests), committed, and pushed. `depop_client.py` now fetches through
Bright Data's Web Unlocker API when `SCRAPER_API_KEY` is set (free tier:
5,000 req/month, 1 credit per successful request, verified 2026-08-19),
falling back to direct fetch when unset. Cron is `*/10` (4,464 runs max
in a 31-day month, under the 5,000 cap). The workflow FAILS LOUDLY (red)
until the `SCRAPER_API_KEY` repo secret exists — deliberate, to avoid
the green-but-blind failure mode. Expect red scheduled runs until the
owner completes the setup steps below.

**Why the move (2026-08-19 findings):** local Task Scheduler hosting
failed two ways. (1) The laptop slept from 2026-08-17 ~21:30 local to
2026-08-19 12:25 local — zero checks all of Aug 18. (2) Local IP got
Cloudflare-403'd far more than the 08-17 handoff believed: 113 of 147
runs on 08-17 were blocked (one 5-hour blind stretch), and 5/5 runs on
08-19 before the session. The "2-min local cadence" was largely
fictional. Owner chose GitHub Actions + free-tier scraper API, accepting
that Actions cron fires late (25-60 min gaps observed historically).

**Alert history is now durable.** Every sent ping appends full content
(UTC timestamp, id, title, price, currency, size, url, image_url) as one
JSON line to `alerts_history.jsonl` (tracked; Actions commits it back).
Before this, only listing IDs were logged — the 4 pings ever sent
(3 on 08-17 14:48 UTC: $17 size 0, $17 size 2, $13 size 2; 1 on 08-17
17:58 UTC: id 871374182, details unrecoverable) predate the history file.

The local task `\DepopPinger\Check Listings` (2-min) is still ENABLED as
a stopgap; it uses direct fetch until the owner puts the token in `.env`.
Disable it once Actions is green for a few days (see Next steps).

## Just completed (this session)

- Diagnosed both hosting failures above (log + Windows event analysis).
- Swapped fetch transport to Bright Data Web Unlocker behind
  `SCRAPER_API_KEY` (`depop_client.py`; RSC parsing untouched). Chose
  Bright Data over ScrapeBadger ($0.15/1k credits, 10 credits/search —
  ~$2-13/mo) and Apify ($39/mo rental actor) because its 5K/month free
  tier is recurring and per-request; owner required free.
- Full ping content logging: INFO log line + `alerts_history.jsonl`
  append in `notifier.py` (write failure never fails the alert).
- Rewrote `.github/workflows/check_listings.yml`: cron `*/10` +
  dispatch, contents:write, missing-secret guard (red run), state
  commit-back (`seen_listings.json` + `alerts_history.jsonl`; also keeps
  the repo active so the 60-day cron auto-disable never triggers).
- `seen_listings.json` un-gitignored and committed (Actions inherits the
  29 locally-seen IDs; note: repo is PUBLIC, so state + alert history
  are publicly visible — owner was told, accepted listing data is
  public anyway; NTFY_TOPIC stays a secret).
- Tests 52 → 59 (new: Bright Data transport, history append).
- CLAUDE.md Scheduling + Data source sections updated.

## In progress / where it stopped

Code complete and pushed. NOT yet verified end to end: no Bright Data
account exists yet, so no live run through Web Unlocker has ever
happened. The exact response Bright Data returns for depop.com search
pages is UNVERIFIED — if its "raw" HTML differs from a direct browser
load in a way that breaks RSC extraction, `DepopResponseSchemaError`
will crash the run (loudly, by design). First verified-green Actions run
is the remaining milestone.

## Next steps, in priority order

1. **Owner: create the free Bright Data account** (brightdata.com, no
   card): create a Web Unlocker zone (note its name; default assumed
   `web_unlocker1`), copy the API token.
2. **Owner: add repo secret** `SCRAPER_API_KEY` = the token (repo →
   Settings → Secrets and variables → Actions). If the zone name isn't
   `web_unlocker1`, also add a repo VARIABLE `BRIGHTDATA_ZONE`.
3. **Owner: add the same token to local `.env`** (`SCRAPER_API_KEY=...`)
   so the stopgap local task stops being 403-blind too.
4. **Verify:** manually dispatch the workflow, confirm the log shows
   "fetch_listings(...): N listings returned" (N > 0), not a schema
   error, and that a state commit-back lands. Then watch a few cron
   firings.
5. **After a few green days: disable the local task**
   (`Disable-ScheduledTask -TaskPath '\DepopPinger\' -TaskName 'Check
   Listings'`, elevated) so the two runners can't double-alert.

## Settled questions (do not re-litigate)

- Hosting = GitHub Actions cron via Bright Data (owner's explicit call,
  2026-08-19; requirement was FREE). Local Task Scheduler is out: laptop
  sleep + residential 403s made it unreliable (numbers above). A paid
  always-on VPS was offered and declined.
- Scraper API = Bright Data Web Unlocker, chosen on price (recurring
  free 5K req/month). ScrapeBadger/Apify comparisons are settled (see
  Just completed) — don't re-shop unless Bright Data's free tier changes.
- Cron = `*/10`, sized to the 5,000/month cap. Don't tighten it without
  re-doing that arithmetic.
- Direct-fetch path stays in `depop_client.py` as the no-key fallback
  (residential IPs only). Everything from the 08-17 handoff about the
  RSC parsing, condition enums, size handling, and criteria stands.
- Old JSON API dead (HTTP 410); data source is the search-page RSC
  payload regardless of transport.

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL criteria knobs + .env loading + scraper API config |
| `depop_client.py` | fetch (direct or Bright Data) + RSC parsing; only file to touch if either changes |
| `notifier.py` | ntfy push + alert history append |
| `alerts_history.jsonl` | full content of every ping sent (tracked, committed back by Actions) |
| `seen_listings.json` | dedupe state (tracked again, committed back by Actions) |
| `.github/workflows/check_listings.yml` | the real scheduler: cron `*/10` + secret guard + commit-back |
| `setup_task.ps1` | local Task Scheduler registration — stopgap only, disable after Actions verified |
| `data\logs\tracker.log` | local runs' log (gitignored); Actions runs log to the Actions console |
| `CRITERIA.md` | expert's answers — the spec behind config.py |
| `tests/` | 59 tests (`test_client_transport.py`, `test_notifier_history.py` new) |

## Operational landmines

1. Scheduled Actions runs are RED on purpose until `SCRAPER_API_KEY` is
   set — that's the guard, not a bug. Don't "fix" it by removing the
   guard; a keyless run can only fetch 0 listings while showing green.
2. A green Actions run still isn't proof of fetching: check the log for
   "N listings returned" with N > 0 (search results are never empty for
   this query; 24 is typical).
3. If the task is ever recreated by hand it reverts to Interactive-only
   + battery-restricted — re-register via `setup_task.ps1` (elevated).
   (Still applies while the local stopgap task exists.)
4. Schema errors from the client = Depop changed their frontend OR
   Bright Data returned something unexpected; fix `depop_client.py`
   only. Transport and parsing are separate functions — check which
   layer broke first.
5. Reconfigure stdout to UTF-8 in any new CLI entry point (emoji in
   listing text crashes bare prints on Windows).
6. Never set ANTHROPIC_API_KEY in this repo's automations (Max-plan rule).
7. Bright Data free tier hard-stops at 5,000 credits/month (resets on
   the 1st, no rollover, no surprise bills). If runs start failing near
   month-end, that's the likely cause — check usage in their dashboard.
8. Notification size shown verbatim, never UK-stripped (UK 8 = US 4).
9. Bare "4"/"6" are NOT excluded terms (collide with size mentions);
   only inch-marked forms. Don't "fix" it.

## Quick health check

```powershell
gh run list --workflow=check_listings.yml --limit 5
git pull; Get-Content alerts_history.jsonl -Tail 5
.venv\Scripts\python.exe -m unittest discover tests
```
Healthy ≈ recent workflow runs green with "N listings returned" (N > 0)
in their logs, state commits landing on main, 59 tests OK. Until the
owner adds the SCRAPER_API_KEY secret: runs red with the guard message
is the expected state.

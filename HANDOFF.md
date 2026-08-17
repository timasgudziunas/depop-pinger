# HANDOFF.md — Session Handoff (updated 2026-08-17 ~14:55 UTC, supersedes all 2026-08-15 and earlier versions)

> For a fresh Claude session with no memory of prior conversations: read
> this file first, then the repo CLAUDE.md for hard constraints (no
> auto-buy, no Cloudflare evasion) and the Scheduling section (local Task
> Scheduler, NOT GitHub Actions), then `depop_client.py`'s module
> docstring if touching the data source. `CRITERIA.md` holds the expert's
> filled-in answers the live config was built from.

## Current state (as of 2026-08-17 ~14:55 UTC)

**The pinger is DONE and LIVE, hosted locally.** Scheduled task
`\DepopPinger\Check Listings` runs `tracker.py` every 2 minutes via the
project venv (registered 14:47 UTC by `setup_task.ps1`: S4U, RunLevel
Highest, wake-to-run, battery-safe, IgnoreNew, 5-min limit). First real
run 14:48 UTC: exit 0, 24 listings fetched, 3 matched, **3 real alerts
delivered** ($17 size 0, $17 size 2, $13 size 2). Wake timers confirmed
enabled on AC and DC. Logs: `data\logs\tracker.log` (rotating, 1MB×3).

**GitHub Actions hosting is RETIRED (2026-08-17).** Root cause: every
scheduled run 2026-08-15→17 (100/100 sampled) got Cloudflare HTTP 403 —
depop.com blocks datacenter IPs, so the cron never fetched a single
listing while showing green (403 is treated as transient → 0 listings →
exit 0). Residential IPs work. The workflow is now `workflow_dispatch`
only, kept as a probe; `seen_listings.json` is local-only and gitignored;
the state-commit-back step is deleted. `NTFY_TOPIC` secret remains set.

Live criteria (from CRITERIA.md, translated 2026-08-17): Speed Up model
only ("speed up"/"speedup" required in text), sizes 0/2/XS/XXS, price cap
$25.00 (item price excl. shipping), condition brand_new/used_like_new/
used_excellent (structured enum; used_good/used_fair rejected), sellers
US+CA, kids excluded, wrong inseam (4"/6") / mid-high rise / liner-removed
/ dealbreaker terms excluded via word-boundary text matching. No color
filter by choice (judge from the photo in the ping). All knobs in
`config.py`; empty list/None disables a check. 52/52 unit tests passing.

Local env: `config.py` now reads the gitignored `.env` itself (stdlib
parser, existing environment wins) so the headless task gets `NTFY_TOPIC`.

## Just completed (this session)

- Translated CRITERIA.md into config + new filters (keywords, exclusions,
  condition, country, kids; structured fields extracted in client).
  Tests 19 → 52. Committed as Phase 8 (`6f49364`).
- Discovered the Actions-Cloudflare blockage; moved hosting to a local
  scheduled task (owner picked this over a scraper API). 2-min cadence
  also beats the cron's real 25-60 min for items that sell in minutes.
- Notifier price formatting ($25 / $23.50) fixed 2026-08-15.
- TODO.md deleted (all steps done); venv created (`.venv`, requests).

## In progress / where it stopped

Nothing in progress. System is live and verified end to end.

## Next steps, in priority order

1. **Watch the first days of alerts** (owner). Tune in `config.py` only:
   spammy → add EXCLUDED_TERMS; missing good listings → likeliest
   culprits are `"style"` (expert-requested but broad) or `"4in"` in
   EXCLUDED_TERMS, or the strict condition list.
2. **Optional:** widen `SEARCH_QUERY` if Depop's search itself misses
   listings (required-keyword filter makes a broader query safe).

## Settled questions (do not re-litigate)

- Hosting = local Task Scheduler. GitHub Actions cannot reach depop.com
  (Cloudflare blocks datacenter IPs; verified across 100 runs). Don't
  re-enable the cron without a successful dispatch probe first.
- Data source = Depop's own search-page RSC payload. Old JSON API dead
  (HTTP 410). Details in `depop_client.py` docstring.
- Condition uses structured `attributes.condition`, not text. Missing
  condition/country passes by design (positive evidence only).
- Bare "4"/"6" are NOT excluded terms (collide with size mentions); only
  inch-marked forms. Don't "fix" it.
- Notification size shown verbatim, never UK-stripped (UK 8 = US 4).

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL criteria knobs + .env loading |
| `filters.py` | pure matching logic incl. `_normalize_text` |
| `depop_client.py` | data source + schema docs; only file to touch if Depop changes |
| `setup_task.ps1` | re-runnable elevated task registration (cadence lives here: 2 min) |
| `data\logs\tracker.log` | per-run log from the scheduled task (gitignored) |
| `seen_listings.json` | dedupe state, local-only, gitignored |
| `CRITERIA.md` | expert's answers — the spec behind config.py |
| `tests/` | 52 tests; `test_client_fixture.py` pins real-config behavior |
| `.github/workflows/check_listings.yml` | manual dispatch probe only |

## Operational landmines

1. If the task is ever recreated by hand (e.g. `schtasks /Create`), it
   reverts to Interactive-only + battery-restricted and silently stops
   firing on sleep/logoff — always re-register via `setup_task.ps1`
   (elevated) instead.
2. Local IP gets Cloudflare 403s after a burst of requests (~4/min
   observed 2026-08-17); a lone 403 self-clears next cycle, but back off
   instead of hammering. At the 2-min cadence this hasn't recurred.
3. The Actions cron is retired for cause — a green probe run does NOT
   mean it fetched anything; check the log for "Checked N listings".
4. Schema errors from the client = Depop changed their frontend; fix
   `depop_client.py` only, or swap to a scraper API (CLAUDE.md option 2).
5. Reconfigure stdout to UTF-8 in any new CLI entry point (emoji in
   listing text crashes bare prints on Windows).
6. Never set ANTHROPIC_API_KEY in this repo's automations (Max-plan rule).
7. Stopping the pinger on purpose = `Disable-ScheduledTask -TaskPath
   '\DepopPinger\' -TaskName 'Check Listings'` (no watchdog to disable).

## Quick health check

```powershell
(Get-ScheduledTaskInfo -TaskPath '\DepopPinger\' -TaskName 'Check Listings') | Select LastRunTime, LastTaskResult, NextRunTime
Get-Content data\logs\tracker.log -Tail 5
python -m unittest discover tests
```
Healthy ≈ LastTaskResult 0 with LastRunTime within ~2 min, log tail shows
"Checked 24 listings" lines (not repeated 403 warnings), 52 tests OK.

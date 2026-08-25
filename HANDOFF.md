# HANDOFF.md — Session Handoff (updated 2026-08-25 ~15:20 UTC, supersedes all 2026-08-23 and earlier versions)

> For a fresh Claude session with no memory of prior conversations: read
> this file first, then the repo CLAUDE.md for hard constraints (no
> auto-buy, no Cloudflare evasion) and its "Data source options" section
> (ScrapeBadger Depop API), then `depop_client.py`'s module docstring if
> touching the data source. `CRITERIA.md` holds the expert's answers
> behind config.py (size 0 only).

## Current state (as of 2026-08-25 ~15:15 UTC)

**LIVE and healthy — but credits nearly exhausted (see Money state).**
Every scheduled Actions run since the ScrapeBadger swap went live
(2026-08-23 19:56 UTC) is green: 65/65 through 14:58 UTC today. All
older red runs in the history are the pre-swap Bright Data era —
expected, not a problem. GitHub cron drift is real: `*/10` actually
fires ~every 30–50 min (~34 runs/day observed 08-24).

No alerts since the swap. Two size-0 candidates were detail-fetched and
correctly rejected (both say "4 inch" — wrong inseam):
`tiffers8c-...-4-inch-size-ed95` (08-25 04:02 UTC) and
`annagran08-red-...-aea8` (08-25 10:03 UTC, description "4 inch inseam
high wasted"). State commit-back is working (`update pinger state
[auto]` commits on origin/main — always `git pull` before reading state
files locally).

Test suite: 81 tests green (one added this session locking the
$25.00-exact prefilter boundary).

## Money state — TOP-UP URGENT

Checked live 2026-08-25 15:05 UTC via `GET /v1/account/me` (free, no
credits): **total_credits_balance = 100**, free tier, 5 req/min. ~30
more were spent on this session's probes, so **~70 credits ≈ 7 API
calls ≈ a few hours of cron remain**. The $10 top-up from the 08-23
handoff never happened. Burn rate at observed cron drift: ~340
credits/day. When credits hit 0, runs go red on search failures — loud,
not silent, and no listings are watched until top-up. **Owner: top up
$10 (~66,000 credits ≈ 6+ weeks) at the ScrapeBadger dashboard now.**

## Just completed (this session, 2026-08-25)

- Investigated the owner's report of a missed size-0 $25 ping from
  08-24. **Verdict: the $25 cap is inclusive at every layer** — see
  Settled questions. The listing was never evaluated (no seen entry, no
  survivor in any run's log), so it was dropped before detail: most
  likely sold within the 30–50 min gap between cron firings (`is_sold`
  cards are prefiltered), or its card `size` wasn't exactly
  "0"/"XXS"/"US 0", or it never reached page 1. If the owner still has
  the listing URL, the exact cause can be pinned down.
- Discovered ScrapeBadger's free balance endpoint `GET /v1/account/me`
  (x-api-key header) and added it to the health check below.
- Added `test_price_exactly_at_ceiling_survives_prefilter` (suite 80→81).

## In progress / where it stopped

Nothing half-built. The only open item is the owner's top-up (above).

## Next steps, in priority order

1. **Owner: top up $10 at ScrapeBadger TODAY** — ~70 credits left as of
   15:15 UTC, dead in a few hours at cron pace.
2. Optional, owner call: add "high wasted" (common misspelling of
   high-waisted, seen live 08-25) to `EXCLUDED_TERMS`. Not added —
   criteria edits go through the owner per standing scope rule.
3. If the missed 08-24 listing's URL turns up, diagnose which drop
   reason applied (sold-between-runs vs card size format vs page-1).

## Settled questions (do not re-litigate)

- **The $25 price cap is INCLUSIVE at every layer** (verified live
  2026-08-25): ScrapeBadger's server-side `price_max=25` returns
  $25.00 cards (probe: sort=priceDescending, top cards exactly 25.00,
  identical with price_max=25.01); the card prefilter drops only
  strictly-over (`> MAX_PRICE`); `filters._matches_price` is `<=`.
  Locked by a regression test. An exactly-$25.00 size-0 listing WILL
  ping. Note: `sort=priceDescending` works on ScrapeBadger search
  (probe-verified), alongside `newest`.
- **Bright Data is dead for depop.com** (compliance block verified
  2026-08-23; KYC business-only). Do not retry.
- **Scraper = ScrapeBadger Depop API** under the $10/month budget;
  competitors have $30–50 minimums. Don't re-shop unless pricing or the
  API breaks.
- Hosting = GitHub Actions cron `*/10` (real cadence ~30–50 min due to
  GitHub drift — accepted). Local hosting is out.
- Criteria are size 0 ONLY (XXS kept as the letter form of 0). Max $25.
- Condition granularity loss (UsedCondition → passes) is accepted;
  photos + text dealbreakers cover it.
- Direct-fetch RSC path stays as the no-key fallback (residential IPs
  only) — also handy free for fetching individual listing pages when
  diagnosing (works from the owner's machine; datacenter IPs get 403).

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL criteria knobs + .env loading + ScrapeBadger config |
| `depop_client.py` | both transports: ScrapeBadger two-step (key set) and direct RSC (no key); the only file to touch if either changes |
| `tracker.py` | orchestration + the "seen = evaluated" semantics writeup |
| `notifier.py` | ntfy push + alert history append |
| `alerts_history.jsonl` | full content of every ping sent (tracked, committed back by Actions) |
| `seen_listings.json` | evaluated-listing state: slugs; numeric ids pre-2026-08-23, aging out. Actions commits it back — pull before reading |
| `.github/workflows/check_listings.yml` | the scheduler: cron `*/10` + secret guard + commit-back |
| `setup_task.ps1` | local Task Scheduler registration — deprecated; task is disabled, leave it disabled |
| `CRITERIA.md` | expert's answers — the spec behind config.py |
| `tests/` | 81 tests; `test_client_transport.py` holds the prefilter + boundary tests |

## Operational landmines

1. Scheduled Actions runs are RED on purpose if `SCRAPER_API_KEY` is
   missing or credits are exhausted — check `GET /v1/account/me` first
   on unexplained red runs.
2. **"0 listings returned" is NORMAL and healthy** (prefilter discards
   non-size-0 cards free). Health signal = "N cards returned" with
   N > 0 (24 typical; 0 cards logs as WARNING).
3. Free-tier rate limit is 5 requests/minute; client sleeps/retries on
   429 (`reset_at`-aware). A run with many new size-0 listings can take
   a few minutes.
4. Do NOT re-enable the local 2-min task while `.env` holds the live
   `SCRAPER_API_KEY` (~300 credits/hour; happened 08-23). It is
   disabled; leave it disabled. ScrapeBadger's `sizes` search param is
   silently ignored (verified 08-23) — size filtering is local-only.
5. If the local task is ever recreated by hand it reverts to
   Interactive-only + battery-restricted — re-register via
   `setup_task.ps1` (elevated). (Moot while disabled.)
6. Schema errors = Depop or ScrapeBadger changed shape; fix
   `depop_client.py` only. Unknown condition strings log WARNING and
   pass — add to `_CONDITION_MAP` once understood.
7. Reconfigure stdout to UTF-8 in any new CLI entry point (emoji).
8. Never set ANTHROPIC_API_KEY in this repo's automations (Max-plan rule).
9. Notification size shown verbatim, never UK-stripped (UK 8 = US 4).
10. Bare "4"/"6" are NOT excluded terms (collide with size mentions);
    only inch-marked forms. Don't "fix" it.
11. Actions commits state back to main — **`git pull` before reading
    `seen_listings.json`/`alerts_history.jsonl` locally**, and before
    pushing.

## Quick health check

```powershell
git pull
gh run list --workflow=check_listings.yml --limit 5
gh run view --log $(gh run list --workflow=check_listings.yml --limit 1 --json databaseId --jq '.[0].databaseId') | Select-String "cards returned"
# credit balance (free call; key is in .env as SCRAPER_API_KEY):
# curl -H "x-api-key: <key>" https://scrapebadger.com/v1/account/me
.venv\Scripts\python.exe -m unittest discover tests
```
Healthy ≈ recent runs green, latest log shows "24 cards returned, N
survived prefilter" (0 survivors normal), 81 tests OK, credit balance
comfortably above ~350 (a day's burn). Red runs = check credits first.

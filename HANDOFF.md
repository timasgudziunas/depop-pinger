# HANDOFF.md

**STATUS: ARCHIVED as of 2026-10-19.** Stale since August 2026, the owner
is no longer using it, and it was quietly spending ScrapeBadger credits every
10 minutes on a watched item nobody was buying.

---

## What was turned off (2026-10-19)

**GitHub Actions cron: OFF.** The `schedule:` block in
`.github/workflows/check_listings.yml` is commented out. `workflow_dispatch`
remains enabled, so a manual run is still possible. Reviving the cron is a
one line uncomment. Important: this cron could NOT have been left to GitHub's
60-day-inactivity auto-disable. The workflow's "Commit state back" step pushes
`seen_listings.json` and `alerts_history.jsonl` to the repo on every run,
which permanently keeps the repo active and prevents that auto-disable from
ever firing. It had to be switched off explicitly.

**No process is running.** Confirmed via `tasklist` on 2026-10-19. The only
live `python.exe` on the machine belongs to a different project.

**Working tree was clean** at commit `2d237dc` dated 2026-08-25, before the
workflow edit.

---

## Open loose end: undeleted Windows scheduled task

The task `\DepopPinger\Check Listings` still EXISTS in Task Scheduler but is
DISABLED. Its last run was 2026-08-23, so nothing is firing. Attempts to
delete it with `schtasks /delete` and `Unregister-ScheduledTask` both returned
"Access is denied" because deletion requires an elevated session.

Owner: run this in an elevated PowerShell to remove it:

```powershell
Unregister-ScheduledTask -TaskPath '\DepopPinger\' -TaskName 'Check Listings' -Confirm:$false
```

Even if the task were somehow re-enabled before deletion, it would fail
harmlessly: once the project folder moves into `archives/`, the task's
configured executable path (`...\projects\depop-pinger\.venv\Scripts\python.exe`)
becomes invalid. `setup_task.ps1` in the repo recreates the task if the
project is ever revived.

---

## Paid service exposure

**ScrapeBadger** (`https://scrapebadger.com`): pay-as-you-go at $0.15 per
1,000 credits. Both search and detail calls cost 10 credits each; failed
requests are free. The API key lives in the GitHub Actions secret
`SCRAPER_API_KEY`. With the `*/10` cron running, search calls alone cost
4,464 x 10 credits = 44,640 credits/month = approximately $6.70/month.
Detail calls add a bounded amount on top.

The cron is now off, so no credits are actively burning. However, the
`SCRAPER_API_KEY` secret is presumably still valid. An unused but live
pay-as-you-go key is the kind of thing that gets forgotten and then either
drains unexpectedly or quietly expires. **Owner: consider revoking the key
or at minimum checking the remaining credit balance at the ScrapeBadger
dashboard.** Balance endpoint (free, no credits): `GET
https://scrapebadger.com/v1/account/me` with header `x-api-key: <key>`.

**ntfy.sh** (`NTFY_TOPIC` secret): ntfy.sh is free for personal use at the
public tier. No billing exposure, but the topic name is still a live secret
in the repo.

No other paid services found in `config.py` or the workflow.

---

## How to revive

1. Uncomment the `schedule:` block in `.github/workflows/check_listings.yml`
   (one line).
2. Confirm `SCRAPER_API_KEY` is still set as a repo secret and the account
   has sufficient credits (top up $10 for approximately 66,000 credits, about
   6 weeks of burn at the $6.70/month search-only baseline).
3. Confirm `NTFY_TOPIC` is still set as a repo secret.
4. If local hosting is wanted instead of Actions: run `setup_task.ps1` in
   an elevated PowerShell. Note the local task must NOT run while the Actions
   cron is also running, both would double-alert and burn credits fast (the
   2026-08-23 incident burned approximately 300 credits/hour from a 2-minute
   local task overlapping with Actions).
5. Optional: expand `SEARCH_QUERY` in `config.py` to catch title variants
   like "lulu speedup" or "align speed up" (the one unchecked item in
   PLAN.md Phase 8).

---

## Retained operational notes (still valid on revival)

**ScrapeBadger API quirks, verified live:**
- The docs say the "newest" sort value is `newlyListed`, but that returns
  HTTP 502. Use `newest` or `newly_listed`.
- The `condition` field on detail responses is a schema.org string
  (`UsedCondition`, `NewCondition`), not the `"Used - excellent"` form the
  docs claim. Finer used grades are not exposed. `UsedCondition` maps to
  unknown and passes; text dealbreakers cover the gap.
- The `sizes` search param is silently ignored server-side (verified
  2026-08-23). Size filtering is local only.
- `price_max` is applied server-side (verified live). The $25.00 ceiling is
  inclusive at every layer: a listing priced exactly $25.00 WILL ping.
- GitHub cron drift is real. The `*/10` schedule actually fired every 30 to
  50 minutes in practice (approximately 34 runs/day observed 2026-08-24).

**"0 listings returned" is normal.** The prefilter discards non-size-0 cards
for free before any detail calls. Health signal is "N cards returned" with N
greater than 0 (24 typical). Zero cards logs as WARNING.

**State semantics changed 2026-08-23:** `seen_listings.json` means "already
evaluated" (detail fetched), not just "already alerted". A given listing only
ever costs one detail call across its lifetime. Always `git pull` before
reading `seen_listings.json` or `alerts_history.jsonl` locally; Actions
commits them back on every run.

**Free tier rate limit:** 5 requests/minute. Client sleeps/retries on 429
using `reset_at`. A run with many new size-0 listings can take a few minutes.

**Bright Data is dead for depop.com.** Compliance-blocked (HTTP 200, empty
body, `x-brd-err-code: policy_20050`). Do not retry.

---

## Where everything lives

| path | what it is |
|---|---|
| `config.py` | ALL criteria knobs and env loading |
| `depop_client.py` | both transports: ScrapeBadger (key set) and direct RSC fallback (residential IPs only) |
| `tracker.py` | orchestration and the "seen = evaluated" semantics |
| `notifier.py` | ntfy push and alert history append |
| `filters.py` | all listing criteria checks |
| `state.py` | seen_listings.json load/save/prune |
| `alerts_history.jsonl` | full content of every ping ever sent (committed back by Actions) |
| `seen_listings.json` | evaluated-listing state, committed back by Actions |
| `.github/workflows/check_listings.yml` | scheduler: cron commented out, workflow_dispatch enabled |
| `setup_task.ps1` | local Task Scheduler registration |
| `CRITERIA.md` | the spec behind config.py (expert answers, size 0 only) |
| `tests/` | 81 tests, all green as of 2026-08-25 |

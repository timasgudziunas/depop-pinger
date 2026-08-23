# CLAUDE.md

Project context and conventions for Claude Code when working in this repo.

## What this project is

A personal notification tool ("depop-pinger") that watches Depop for new
listings matching a specific set of criteria — Lululemon Speedup shorts in
specific sizes — and sends a push notification the moment a matching listing
goes live. It does **not** purchase anything automatically. A human always
logs in, evaluates the item, and buys it manually. Speed matters because
matching listings sell within minutes.

This is a sibling project to `ticket-sniper` (SeatGeek price alerts) and
reuses the same overall shape: poll a source on a schedule → filter by
criteria → dedupe against previously-seen items → push a notification for
anything new → persist state → repeat via GitHub Actions cron.

## Hard constraints

- **No auto-checkout, no auto-add-to-cart, no CAPTCHA solving, no login
  automation for purchasing.** The scope is strictly detection + alerting.
- **Respect Depop's rate limits and ToS as much as practically possible.**
  Depop has no official public API and is Cloudflare-protected, so:
  - Poll interval should never be more aggressive than every 60 seconds. 90–120s
    is the safer default for a long-running personal script.
  - Prefer the lowest-friction working data source (see "Data source options"
    below) rather than aggressive raw scraping.
  - Set a realistic browser-like User-Agent, but do not attempt to bypass
    Cloudflare challenges, rotate proxies to evade blocking, or spoof
    anti-bot tokens. If the chosen approach gets consistently blocked, stop
    and re-evaluate the data source rather than escalating evasion.
- Never commit API keys, tokens, or the ntfy.sh topic name (if treated as
  secret) to the repo. Use GitHub Actions secrets.

## Data source options (pick one in PLAN.md Phase 2)

1. **Depop's own search — mimicked as a browser request.** Same approach
   Depop's own web app uses when you search on depop.com. Free, but brittle:
   response shape can change without notice and may get rate-limited or
   Cloudflare-challenged under sustained polling. Used as the local fallback
   fetch path when `SCRAPER_API_KEY` is unset (works on residential IPs
   only).
2. **Third-party scraper API — LIVE as of 2026-08-23 (ScrapeBadger).**
   `depop_client.py` routes through ScrapeBadger's dedicated Depop API
   (`https://scrapebadger.com/v1/depop`) when `SCRAPER_API_KEY` is set.
   This replaced Bright Data Web Unlocker the same day: Bright Data
   compliance-blocks depop.com outright (returns HTTP 200 with an empty
   body and an `x-brd-err-code: policy_20050` header — "target site
   requires special permission"), and their KYC path to unblock it is
   business-only, not available to a personal account. So this is a
   different kind of transport, not just a different vendor of the same
   thing: ScrapeBadger returns structured JSON (no page HTML to scrape),
   via two calls per surviving candidate listing —
     1. `GET /search` (10 credits) returns lightweight "cards": slug, size,
        price, is_sold, image — no listing id, no title, no condition.
     2. `GET /products/{slug}` (10 credits) returns the rest: title,
        description, condition. No size field on detail — size only comes
        from the search card.
   Cards are prefiltered for free (sold / already-evaluated / wrong size /
   over price) before spending a detail call, and detail calls are capped
   per run at `config.MAX_DETAIL_FETCHES_PER_RUN` (8) since they're the
   rate-limited, paid part (free tier: 5 requests/minute). `seen_listings.json`
   now means "already evaluated" (detail fetched, whether or not it
   matched), not just "already alerted" — see tracker.py's module
   docstring — so a given listing only ever costs one detail call across
   its lifetime.
   Pricing: pay-as-you-go, $0.15 per 1,000 credits, failed requests free.
   At the `*/10` cron (4,464 searches/31-day month) that's already
   4,464 × 10 = 44,640 credits ≈ $6.70/month on search calls alone, inside
   the owner's approved $10/month budget (detail calls add a bounded amount
   on top). Two known API quirks worth flagging for whoever touches this
   next: the docs claim the "newest" sort value is `newlyListed`, but that
   returns HTTP 502 live — `newest` (or `newly_listed`) is what actually
   works. And `condition` on the detail response is a schema.org-style
   string (`UsedCondition`, `NewCondition`), not the docs' claimed
   `"Used - excellent"` form, and it doesn't expose the finer used_* grades
   Depop itself has — `UsedCondition` maps to unknown/passes rather than
   guessing a grade, and the text dealbreakers + a human looking at photos
   before buying are relied on to cover that gap.
   This is what makes GitHub Actions hosting viable again (see Scheduling
   below) — GitHub's datacenter IPs are Cloudflare-blocked hitting
   depop.com directly, but ScrapeBadger's IPs aren't.

`depop_client.py` remains the only file that needs to change if the
transport is swapped again.

## Repo structure

```
depop-pinger/
├── config.py              # search keywords, target sizes, price ceiling, poll interval
├── depop_client.py        # fetches current listings for the search criteria
├── filters.py             # matches listings against config criteria
├── state.py                # tracks which listing IDs have already been evaluated (seen_listings.json)
├── notifier.py             # sends ntfy.sh push notifications
├── tracker.py               # orchestrates: fetch -> filter -> dedupe -> notify -> save state
├── setup_task.ps1          # registers the local Task Scheduler task (deprecated, see Scheduling)
├── seen_listings.json      # persisted state, tracked in git again (committed back by Actions)
├── alerts_history.jsonl    # tracked, full content of every ping ever sent (one JSON obj/line)
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── check_listings.yml   # the real scheduler again — see Scheduling below
```

## Scheduling (changed 2026-08-19, scraper vendor changed again 2026-08-23)

Hosting moved BACK to GitHub Actions cron (`.github/workflows/check_listings.yml`,
every 10 minutes) as of 2026-08-19, once `depop_client.py` started fetching
through a scraper API instead of hitting depop.com directly — GitHub's
datacenter IPs never touch depop.com anymore, so the 2026-08-17 Cloudflare
403 blocks that forced the move to local hosting no longer apply. That
scraper API is ScrapeBadger as of 2026-08-23 (Bright Data Web Unlocker,
used 2026-08-19 through 2026-08-23, was abandoned — see "Data source
options" above); the hosting rationale is unchanged, only the vendor
behind `SCRAPER_API_KEY` is different. The workflow commits
`seen_listings.json` and `alerts_history.jsonl` back to the repo after each
run.

The local Windows Task Scheduler task (`\DepopPinger\Check Listings`,
registered by `setup_task.ps1`) is deprecated and still exists only until
the Actions cron is confirmed green for a few days; disable it once
verified so the two runners don't double-alert.

## Conventions

- Python 3.11+, standard library + `requests` — keep dependencies minimal,
  same as ticket-sniper.
- All tunable criteria (sizes, price ceiling, keywords, poll interval) live
  in `config.py` as plain constants with comments — no hidden magic numbers
  in `tracker.py` or `filters.py`.
- `config.py` sizes and price ceiling should ship as clearly marked
  placeholders (e.g. `TARGET_SIZES = []  # TODO: fill in with Timas's gf`)
  until the real criteria are confirmed.
- State (`seen_listings.json`) is the source of truth for "already
  evaluated" (changed 2026-08-23 with the ScrapeBadger swap — see
  tracker.py's module docstring): never re-fetch detail for or re-notify on
  a listing ID already present in it. Prune entries older than ~14 days so
  the file doesn't grow unbounded.
- Notifications should include: item title, price, size (if parseable),
  and a direct link to the listing.
- Secrets (ntfy topic if private, any scraper API key) go in GitHub Actions
  secrets and are read via environment variables — mirror the pattern from
  ticket-sniper's `.github/workflows/check_prices.yml`.

## Testing

- `depop_client.py` should be testable against a saved sample response
  (fixture JSON) so filter logic can be verified without hitting Depop live
  on every test run.
- Before wiring up the GitHub Actions cron, do a manual local run with a
  broad/no-op filter to confirm the client successfully returns listings at
  all — confirms the data source is working before criteria are added.

## Out of scope for this repo

- Any form of automated purchasing, cart automation, or checkout.
- Solving or bypassing CAPTCHA/Cloudflare challenges.
- Reselling analytics, pricing suggestions, or inventory tracking — this is
  alerting only.

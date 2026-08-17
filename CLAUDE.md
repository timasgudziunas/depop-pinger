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
   Cloudflare-challenged under sustained polling.
2. **Third-party scraper API** (e.g. ScrapeBadger, Apify Depop actors,
   Retailed) that handles Cloudflare/proxies for you and returns structured
   JSON (query, brand, size, price filters built in). Usually has a free
   tier sufficient for personal polling volume; more resilient than #1 but
   adds an external dependency and possibly a paid API key.

Default recommendation: start with option 1 for simplicity; if it proves
unreliable (frequent blocks/empty responses), swap in option 2 without
changing the rest of the architecture — `depop_client.py` should be the only
file that needs to change.

## Repo structure

```
depop-pinger/
├── config.py              # search keywords, target sizes, price ceiling, poll interval
├── depop_client.py        # fetches current listings for the search criteria
├── filters.py             # matches listings against config criteria
├── state.py                # tracks which listing IDs have already been alerted on
├── notifier.py             # sends ntfy.sh push notifications
├── tracker.py               # orchestrates: fetch -> filter -> dedupe -> notify -> save state
├── setup_task.ps1          # registers the local Task Scheduler task (the real scheduler)
├── seen_listings.json      # persisted state, local-only + gitignored (since 2026-08-17)
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── check_listings.yml   # manual probe only — see Scheduling below
```

## Scheduling (changed 2026-08-17)

The pinger runs locally via Windows Task Scheduler (`\DepopPinger\Check
Listings`, every 2 minutes, registered by `setup_task.ps1`), NOT on GitHub
Actions. The original Actions cron never worked: every scheduled run from
2026-08-15 to 2026-08-17 was Cloudflare-403-blocked because depop.com
blocks datacenter IPs. Residential IPs are fine. The workflow file is kept
as a `workflow_dispatch`-only probe for re-testing whether GitHub IPs are
still blocked. Do not re-enable the cron without confirming the probe
fetches listings.

## Conventions

- Python 3.11+, standard library + `requests` — keep dependencies minimal,
  same as ticket-sniper.
- All tunable criteria (sizes, price ceiling, keywords, poll interval) live
  in `config.py` as plain constants with comments — no hidden magic numbers
  in `tracker.py` or `filters.py`.
- `config.py` sizes and price ceiling should ship as clearly marked
  placeholders (e.g. `TARGET_SIZES = []  # TODO: fill in with Timas's gf`)
  until the real criteria are confirmed.
- State (`seen_listings.json`) is the source of truth for "already alerted" —
  never re-notify on a listing ID already present in it. Prune entries older
  than ~14 days so the file doesn't grow unbounded.
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

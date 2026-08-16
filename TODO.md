# TODO.md

Three setup steps left before the pinger can actually ping. Do them in
order during the next session. Each takes a couple of minutes.

## 1. Subscribe to the ntfy topic on your phone

* Install the ntfy app (free, App Store or Play Store) if not installed.
* In the app, tap the plus button and subscribe to the topic name stored
  in this repo's local `.env` file (gitignored on purpose, the topic name
  works like a password: anyone who knows it can send you pushes, so it
  never goes in a committed file).
* Optional but recommended: in the app, set this topic's priority so
  alerts break through Do Not Disturb, since speed matters here.

## 2. Confirm a test push lands on your phone

* From the repo folder, run: `python notifier.py`
* It sends one fake "Lululemon Speedup Shorts" alert to your topic.
* Success means: notification appears on the phone, shows title, price,
  and size, and tapping it opens a Depop listing URL.
* If nothing arrives, check that the topic in the app exactly matches the
  `.env` value, then rerun.

## 3. Log in to gh and set the repo secret

* Run `gh auth login` in the terminal (in a Claude session, type
  `! gh auth login` so the interactive login runs properly).
* Then set the secret so the GitHub cron can send alerts:
  `gh secret set NTFY_TOPIC` and paste the same topic value from `.env`.
  (Web UI alternative: repo Settings, then Secrets and variables, then
  Actions, then New repository secret named `NTFY_TOPIC`.)
* Then trigger one manual run to verify green end to end:
  `gh workflow run check_listings.yml` or use the Actions tab.
* Important: until this secret exists, any scheduled run that finds a new
  listing will fail loudly (red X in Actions) instead of alerting. The
  cron is already live, so do this step soon.

After these three, the only thing left is filling in the real search
criteria in `config.py`. That is what `CRITERIA.md` is for: send it to
the expert, get the answers back, and the next session translates them
into config values.

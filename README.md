# Poly — Polymarket value-betting agent (cloud edition)

Scans Polymarket's 2026 FIFA World Cup markets 3x/day **in the cloud** and pushes
a notification to your phone only when a market looks genuinely mispriced versus
consensus sportsbook odds and current news. Runs on GitHub Actions, so it works
with your laptop off. The default alert channel (Discord) is **free**.

It is an informational research tool, **not financial advice**, and it never
places bets. Always confirm price/availability in your Polymarket US app and bet
responsibly.

## Files
- `value_scout.py` — the scan + analysis + SMS logic
- `requirements.txt` — Python deps (`anthropic`, `requests`)
- `value-scout.yml` — the GitHub Actions schedule (goes in `.github/workflows/`)

## One-time setup (~15 min)

### 1. Create the repo
1. Make a new **private** GitHub repo (e.g. `value-scout`).
2. Add these files to it:
   - `value_scout.py` and `requirements.txt` at the repo root
   - `value-scout.yml` at `.github/workflows/value-scout.yml`

### 2. Get your keys
- **Anthropic API key** — console.anthropic.com → API Keys. Add a few dollars of
  credit; at 3 runs/day with web search this is a small monthly cost. (This is
  the only paid piece; the alert channel below is free.)
- **Phone alerts — pick ONE free option:**
  - **Discord (recommended).** Install the Discord app on your phone. In any
    server you own (make one in 10 seconds), go to a channel →
    **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL.**
    That URL is your alert channel. Turn on notifications for that channel on
    your phone. Free.
  - **ntfy.sh (zero signup).** Install the **ntfy** app, pick a hard-to-guess
    topic name (e.g. `poly-jr-7f3k`), and "subscribe" to it in the app. Free, no
    account.

### 3. Add repo secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret.**
Add `ANTHROPIC_API_KEY`, plus **one** alert secret:

| Secret name           | Value                                              |
|-----------------------|----------------------------------------------------|
| `ANTHROPIC_API_KEY`   | your Anthropic key                                 |
| `DISCORD_WEBHOOK_URL` | the Discord webhook URL (if using Discord)         |
| `NTFY_TOPIC`          | your ntfy topic name (if using ntfy instead)       |

The script checks Discord first, then ntfy, then Twilio. Only set the one you
want. (Twilio SMS is still supported if you ever want paid texts — set
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `ALERT_TO_PHONE`.)

### 4. Test it
- Go to the **Actions** tab → **Polymarket Value Scout** → **Run workflow**
  (manual trigger). Watch the run log.
- To test without sending a text, add a temporary repo secret `DRY_RUN` = `1`
  (the script prints the SMS instead of sending). Remove it to go live.

That's it — it now runs automatically on the schedule, laptop or not.

## Schedule / timezone
The cron in `value-scout.yml` is **UTC** and is preset for US Eastern during the
World Cup (7:30a / 12:30p / 5:30p ET → `30 11,16,21 * * *`). GitHub cron does not
observe Daylight Saving, so adjust the hours if your timezone differs or after a
DST change. (GitHub may also delay scheduled runs by a few minutes under load.)

## Tuning (optional)
Set these as repo secrets or edit the env block in `value-scout.yml`:
- `MIN_EDGE_PP` — min edge in percentage points to alert (default `4`). Raise it
  for fewer, higher-conviction alerts.
- `MIN_LIQUIDITY` / `MAX_SPREAD` — quality filters on which markets to consider.
- `MARKET_TAG` — defaults to `world-cup`. Change it (e.g. `soccer`, `nba`,
  `politics`) to expand scope later. You can also duplicate the workflow with a
  different tag.
- `ANTHROPIC_MODEL` — defaults to `claude-sonnet-4-6`.

## How "good bet" is decided
For each liquid market the script asks Claude (with live web search) to:
1. Pull consensus sportsbook odds for the same outcome and **de-vig** them into a
   fair probability.
2. Check the last 24-48h of news (injuries, lineups, results) and discard any gap
   that's just stale odds.
3. Flag only outcomes where Polymarket's price is below fair value by at least
   `MIN_EDGE_PP`, backed by 2+ sources. It is designed to flag nothing on most
   runs rather than force a pick.

## Notes & limits
- GitHub disables scheduled workflows after ~60 days of **no repo activity** — push
  a commit occasionally, or trigger a manual run, to keep it alive.
- The public Gamma API serves Polymarket's global catalog; the US-regulated app's
  catalog/pricing can differ, so always confirm in your app before betting.
- Cost: with Discord or ntfy the only cost is Anthropic API usage (small at 3
  runs/day, but real — keep an eye on it). Discord/ntfy alerts are free.

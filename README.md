# 🐋 Moby

**A multi-factor smart-money sentiment agent for Polymarket.** Moby runs in the
cloud on a schedule, reads where the **biggest and sharpest money** is positioned
across a sport's markets, blends in news and your own track record, and pushes a
**daily slate of bets** — broken into game props, player props, and futures —
straight to your phone via Discord.

It's **multi-sport**: one sport (soccer / World Cup) ships today, WNBA is wired
as a reference adapter, and adding another is a single small profile file (see
[Adding a sport](#adding-a-sport)). Each active sport posts to its own Discord
channel, and all of them share one cheap analysis pass per run.

It is an informational research tool. **It is not financial advice and it never
places bets.** Always confirm price and availability in your own Polymarket app,
and bet responsibly.

---

## What makes Moby different

Most tools hunt for "mispricings" against sportsbooks. Moby doesn't. It reads
**sentiment** — specifically, what the people with money and a track record are
actually doing — and weighs several independent factors into each pick.

### The factors

| # | Factor | Source | Weight |
|---|--------|--------|--------|
| 1 | **Smart money** | Largest current holders per outcome (`/holders`), weighted by dollars at risk | Primary |
| 2 | **Sharp money** | Those holders cross-referenced against the all-time profit **leaderboard** (`/v1/leaderboard`) and re-weighted by lifetime PnL | Primary (highest quality) |
| 3 | **News / public sentiment** | Live web search (injuries, form, lineups, momentum) | Secondary |
| 4 | **Track record** | Moby's own past picks, graded win/loss as their markets resolve | Calibration |
| 5 | **X / social feed** | Wired as an input slot — *coming soon* | Planned |

**Sharp money is the headline idea.** A market where one side is merely *big* is
a weak signal. A market where Polymarket's *historically profitable whales* are
piled on one side is a strong one. Moby weights each holder by lifetime PnL
(a $1M+ all-time winner counts 4× a no-name position), so a single proven sharp
can outweigh a crowd of size. When raw money and sharp money **disagree**, Moby
trusts the sharp side and flags the divergence.

### The output: a daily slate

Every run produces up to ~3 picks in each bucket — **game props → player props →
futures** — each with its conviction and the factors behind it. Empty buckets are
allowed: Moby won't invent a pick when the factors don't support one.

---

## How a run works

Each run walks a **four-stage pipeline**, front-loading all the free code so the
model only ever reads a small, curated view. Every active sport is prepared
independently, then rides **one shared model batch**:

```
Gamma API ──▶ pull the sport's markets, classify & prioritize
                (game props → player props → futures; games before the
                 next scheduled run first — their only shot at a bet)
                         │
Data API ─────▶ for each market, pull top holders per outcome
   /holders                │
Data API ─────▶ pull all-time profit leaderboard → "sharp" wallet set
   /v1/leaderboard         │
                ┌──────────┴───────────┐
                ▼                      ▼
        raw $ positioning      PnL-weighted (sharp) positioning
                └──────────┬───────────┘
                           ▼
  ── Stage A (code, $0) ── cap to PREFILTER_TOP_N + compact each market
                           ▼
  ── Stage B (Haiku+search) ── news brief, ONLY when this window owns games
                           ▼
  ── Stage C (Sonnet, no tools) ── all active sports in ONE Messages Batch
                           │           (50% off tokens) synthesize the slate
                           ▼
  ── Stage D (code, $0) ── prune / tag / size units / render / send / log
                           ▼
        Daily slate → Discord  +  signals_log.jsonl (for grading)
```

The [staged cost engine](#the-staged-cost-engine) explains why it's split this
way — the short version is that curating the input in code buys Sonnet-class
reading for roughly what a degraded Haiku run used to cost.

---

## Layout

Moby used to be one 1,387-line `moby.py`. It's now a package; `moby.py` is a
thin shim so the workflow command (`python moby.py`) is unchanged. The package
re-exports its full public surface, so `import moby; moby.clean_markets(...)`
still works exactly as before.

| Path | Purpose |
|------|---------|
| `moby.py` | Thin entrypoint shim → `moby.pipeline.main()` |
| `moby/pipeline.py` | The run orchestrator: fault-isolated multi-sport flow (prepare → shared batch → finish) |
| `moby/llm.py` | Claude tiers + the staged model flow (news brief, synthesis batch, cost estimate) |
| `moby/prefilter.py` | Stage A — cap to `PREFILTER_TOP_N` and compact each market to the fields the model reasons over |
| `moby/prompts.py` | The prompt template + the shared/cacheable synthesis system blocks |
| `moby/markets.py`, `smartmoney.py`, `polymarket.py` | Fetch, classify, sharp-money weighting, Gamma/Data API clients |
| `moby/picks.py`, `render.py`, `alerts.py`, `tracklog.py` | Stage D: prune/tag/size, Discord payload, dispatch, signal logging |
| `moby/windows.py`, `factors.py`, `config.py` | Run-window math, track-record/X factors, env-knob precedence |
| `moby/sports/` | The sport adapters — `base.py` (the `SportProfile` contract), `soccer.py`, `wnba.py`, `mlb.py`, ..., `__init__.py` (registry) |
| `tests/` | The pytest suite (see [Testing](#testing)); `tests/fixtures/` holds the golden Discord payloads |
| `.github/workflows/moby.yml` | The 3×/day schedule + Discord failure alert; restores/persists the track record on the `data` branch |
| `.github/workflows/ci.yml` | Fast check on every push (`pytest -q` + `py_compile`) |
| `signals_log.jsonl` | The track record: every pick logged with `condition_id` (and its `sport`) so it can be graded later. **Lives on the dedicated `data` branch, not `main`** — the workflow restores it before each run and force-pushes the updated log back after, so automated log commits never touch `main`. Git-ignored on `main`. |

---

## Adding a sport

A new sport is **one profile file + one webhook secret + one registry entry** —
no edits to any core module. The contract is `SportProfile` in
`moby/sports/base.py`; `moby/sports/wnba.py` is the worked reference.

1. **Write the profile.** Copy `wnba.py`, set `key` (the env/log/CLI id),
   `label` (Discord header + prompt subject), `market_tag` (the Polymarket
   Gamma tag), the classify hint tuples (`game_strong` / `player_hints` /
   `future_hints` / `novelty`), the in-play `sport_prompt`, and `search_hints`.
   Thin-liquidity sports set per-sport `defaults` (e.g. WNBA drops `MIN_LIQUIDITY`
   to `250`, `MIN_SMART_MONEY_USD` to `1000`); env vars still override them.
2. **Register it.** Add the profile to the `SPORTS` map in
   `moby/sports/__init__.py`.
3. **Wire the channel.** Set the `DISCORD_WEBHOOK_URL_<SPORT>` secret named by
   the profile's `webhook_env`, then add the sport's key to `MOBY_SPORTS`.

That's it — the pipeline picks it up. An unknown key in `MOBY_SPORTS` is a
**startup error**, not a silent skip, so a half-registered sport fails loudly
before any network work. (UFC / NFL / NBA adapters are planned as their seasons
open — each is expected to be one more small profile file.)

The classify hints are the fiddly part. Order matters: `game_strong` is scanned
against `question + event` **before** `player_hints`. WNBA is the cautionary
tale — its player props read `"Points Over 21.5"`, so a bare `"over "`/`"under "`
in `game_strong` would swallow every player prop; it uses compound totals
phrases (`"total points over"`) instead and keeps the stat words in
`player_hints`. Validated against live Polymarket WNBA data (531 markets, 0
unclassified).

---

## The staged cost engine

The model never sees the raw market dump. Free code curates the input first, so
the paid stages read a small, high-value view. The four stages:

| Stage | Cost | What it does |
|-------|------|--------------|
| **A — prefilter** | code, $0 | The markets are already ranked (last-chance first, strongest sharp signal first); this caps to `PREFILTER_TOP_N` (30) and compacts each to the handful of fields the model reasons over. Raw holder tables, internals, and IDs stay out — junk out, room for real context in. |
| **B — news brief** | Haiku + web search | A short factual scouting brief (injuries, lineups, form, public lean) from `MODEL_NEWS` (default `claude-haiku-4-5-20251001`), up to `NEWS_MAX_SEARCHES` (5) searches. **Only runs when the window actually owns games** (has last-chance markets) — otherwise there's nothing to scout and it's skipped. |
| **C — synthesis** | Sonnet, no tools | `MODEL_SYNTH` (default `claude-sonnet-4-6`) reads the curated view + news brief + track record + X slot and returns the slate. **All active sports go out as ONE Messages Batch** (50% off all tokens; `custom_id` = the sport key), polled up to `BATCH_WAIT_MIN` (20) min. If the batch stalls it's cancelled and each sport falls back to a direct call, so an alert always ships. `BATCH_MODE=0` forces direct calls. The system prompt's shared base block carries `cache_control`, so a multi-sport batch reuses the cached prefix. |
| **D — finalize** | code, $0 | Prune zero/low-upside picks, tag contrarian/hedge, size the suggested units (fractional Kelly), render, send, and log — unchanged from before. |

**Why bother:** curating in code buys **Sonnet-class reading on a small input**
at roughly what a *degraded* Haiku run cost before — about **$0.10/sport-run**,
call it **$15–22/mo** at a full five-sport peak. Search happens in exactly one
place (Stage B), gated on whether the window even has games to scout.

---

## One-time setup (~15 min)

### 1. Keys & alert channel
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com) → API Keys. Add a few dollars of credit.
- **Phone alerts — pick ONE free option:**
  - **Discord (recommended):** in a server you own, a channel → **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL**, then enable notifications for that channel on your phone.
  - **ntfy.sh (no signup):** install the **ntfy** app, pick a topic, subscribe to it.

### 2. Repo secrets
**Settings → Secrets and variables → Actions → New repository secret.**

| Secret | Required | Value |
|--------|----------|-------|
| `ANTHROPIC_API_KEY` | ✅ | Your Anthropic key |
| `DISCORD_WEBHOOK_URL` | one alert channel | Discord webhook URL — soccer's channel **and** the ops/failure channel |
| `DISCORD_WEBHOOK_URL_<SPORT>` | per extra sport | Per-sport channel, e.g. `DISCORD_WEBHOOK_URL_WNBA`. Unset (or empty) falls back to `DISCORD_WEBHOOK_URL`, so it's harmless to leave until you turn the sport on |
| `NTFY_TOPIC` | (alt) | Your ntfy topic |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM` / `ALERT_TO_PHONE` | (alt, paid) | Twilio SMS |

Alert channels are checked in order: **Discord → ntfy → Twilio.** Each active
sport posts to its **own** Discord channel via `DISCORD_WEBHOOK_URL_<SPORT>`
(matching the profile's `webhook_env`); anything unset falls back to the legacy
`DISCORD_WEBHOOK_URL`.

### 3. Test it
**Actions** tab → **Moby** → **Run workflow**. The dispatch form has two
inputs:
- **`dry_run`** — set to `1` to print the slate to the log instead of posting
  to Discord (nothing is sent).
- **`test`** — set to `1` to post to Discord **for real** but with a
  `🧪 TEST ·` badge on the header and **no signal logging**, so a validation
  slate is unmistakable in the channel and never enters the track record.
  Combine with `dry_run=1` and the dry-run wins (nothing posts).

---

## Tuning (all optional)

Set as repo secrets or edit the `env:` block in `moby.yml`:

| Variable | Default | What it does |
|----------|---------|--------------|
| `MARKET_TAG` | `fifa-world-cup` | Which Polymarket tag to scan (this tag includes the live per-match markets **and** futures; the bare `world-cup` tag has only tournament-level futures) |
| `EVENT_FETCH_LIMIT` | `200` | How many events to pull from Gamma (paginated). Higher = deeper reach so **upcoming games' full prop menus** are included, not just their moneyline |
| `MARKET_CAP` | `100` | Markets analyzed per run |
| `FUTURES_SLOTS` | `4` | Slots reserved for futures vs props |
| `MAX_GAME_PROPS_PER_GAME` | `30` | Cap on game props from any single match — high enough to cover a game's full standard menu, while trimming the tail (every corner/exact-score line) so one game can't crowd out the others |
| `MAX_PLAYER_PROPS_PER_GAME` | `15` | Same cap for player props per match |
| `WINDOW_HOURS` | `18` | Outer reach of a run's slate. Games before the **next scheduled run** are prioritized (last chance — their only shot); games after it are fallback only |
| `NEXT_RUN_BUFFER_MIN` | `60` | Minutes of grace past the next run when deciding which games are "last chance." Absorbs GitHub's scheduler drift so a game right around the next run isn't missed |
| `MIN_SMART_MONEY_USD` | `2000` | Skip markets with little big-money interest |
| `MIN_LIQUIDITY` / `MAX_SPREAD` | `500` / `0.07` | Quality filters on markets |
| `KELLY_FRACTION` | `0.25` | Fraction of full Kelly used to size the suggested stake. Lower = more conservative |
| `MAX_UNITS` | `5` | Cap on the suggested stake (1 unit = 1% of bankroll) |
| `X_BEARER_TOKEN` | — | Reserved for the upcoming X/Twitter sentiment feed |

**Multi-sport & the model tiers** (see the sections above for the why):

| Variable | Default | What it does |
|----------|---------|--------------|
| `MOBY_SPORTS` | `soccer` | Comma-separated sport keys to run this cycle (the workflow sets all six: `soccer,wnba,ufc,nfl,nba,mlb`). An unknown key is a startup error |
| `REQUIRE_GAME_WINDOW` | `1` | The season gate: a sport only proceeds when it has a live game or one starting within `WINDOW_HOURS` — futures-only sports (NFL in July) quiet-exit at $0, before the holder fetches. `0` disables |
| `TEST_RUN` | `0` | `1` = post with the `🧪 TEST` header badge and skip signal logging (set automatically by the `test` dispatch input) |
| `MODEL_SYNTH` | `claude-sonnet-4-6` | Stage C synthesis model. The legacy `ANTHROPIC_MODEL` secret is still honored for this if `MODEL_SYNTH` is unset |
| `MODEL_NEWS` | `claude-haiku-4-5-20251001` | Stage B news-brief model (Haiku + web search) |
| `BATCH_MODE` | `1` | `0` forces per-sport direct synthesis calls instead of the shared Messages Batch |
| `BATCH_WAIT_MIN` | `20` | Minutes to poll the synthesis batch before cancelling + falling back to direct calls |
| `PREFILTER_TOP_N` | `30` | Stage A cap: how many ranked markets survive into the model's view |
| `NEWS_MAX_SEARCHES` | `5` | Web-search cap on the Stage B news brief |

Knob precedence is **env var > profile `defaults` > global default** (see
`moby/config.py`), so a repo secret always wins, and a sport can lower a floor
for itself without a secret.

---

## Stake sizing (units)

Each pick includes a suggested **stake in units**, where **1 unit = 1% of your
bankroll** (a bankroll-agnostic way to size bets — see any sports-betting
"units" explainer). It's computed **mathematically, not guessed**, from two
things already on every pick: **conviction** and **price**.

- The pick's **price** is treated as the market's implied win probability, and
  **conviction** adds a small assumed edge on top (High +5, Medium +3, Low +1.5
  percentage points).
- That edge + the pick's odds go through the **Kelly criterion** (`f* = p −
  (1−p)/b`), and Moby stakes a conservative **quarter of Kelly** (`KELLY_FRACTION`),
  floored at 0.5u and capped at `MAX_UNITS`.

Because it's Kelly-based, sizing is inherently payoff-aware: it **sizes down**
high-variance longshots, **sizes up** confident, well-priced edges, and suggests
**nothing** when there's no positive edge. A ½-unit "lean" and a 4-unit "lock"
carry Moby's confidence in a number you can act on — scaled to *your* bankroll,
whatever its size. **Not financial advice; bet responsibly.**

---

## The track record (self-grading)

Moby logs every pick to `signals_log.jsonl` **with the market's `condition_id`**.
On later runs it re-checks those markets via the Gamma API; once a market
resolves, the pick is graded **win or loss**. That record — overall and per
bucket — is fed back into the model to **calibrate conviction** (lean into
buckets that are hitting, ease off ones that aren't).

It starts empty. Until some logged picks' markets resolve, Moby honestly reports
"track record still building" — that's expected, not a bug.

---

## Schedule / timezone

The cron in `moby.yml` is **UTC** (`20 11,16,21 * * *`), deliberately set ~1h10m
early to absorb GitHub's typical ~1-hour scheduler drift — so alerts land around
**7:20a / 12:20p / 5:20p Central**. GitHub cron ignores Daylight Saving; nudge
the cron hours for your timezone or after a DST change. Scheduled runs can also
drift under load.

Moby's **internal** slot/window math (which run "owns" which games, the Central
labels on the header) now derives Central time from `zoneinfo("America/Chicago")`,
so it stays correct across the DST boundary on its own — only the cron line needs
a manual nudge.

---

## Cost

- **Anthropic API** is the only paid piece — roughly **$0.10 per sport-run** now
  that the staged engine feeds Sonnet a small curated view (and batches all
  sports at 50% off). Call it **~$15–22/mo** at a full five-sport peak; a lot
  less with just soccer. Each stage logs its exact estimated cost.
- **Polymarket Gamma + Data APIs** are free and need no key.
- **Discord / ntfy** alerts are free.

See [The staged cost engine](#the-staged-cost-engine) for how the number stays
low: curate in code, search in one gated place, batch the synthesis.

---

## Testing

The suite is real pytest (`tests/`), run on every push by CI (`pytest -q` +
`py_compile`). Locally:

```
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Everything runs **offline** — no network, no API calls. Coverage spans classify,
sharp-weighting, the window math, the sport-adapter contract, the WNBA hint
ordering, and the public re-export surface.

**The golden Discord payload.** `tests/test_render_golden.py` pins the rendered
Discord JSON **byte-for-byte** against `tests/fixtures/golden_*_payload.json`
(both a full slate and a no-picks run). This is the guard that the phone output
never drifts by accident. If you *deliberately* change the payload format, that
test will fail — regenerate the fixtures with:

```
python tests/fixtures/regenerate_golden.py
```

and commit the new goldens **only** when the diff is the change you intended.
Regenerating to make a red test green without reading the diff defeats the
entire point.

---

## Validating from a branch

You can exercise the whole workflow from a non-`main` branch without touching
production:

- **`workflow_dispatch` with `dry_run=1`** runs every stage but **posts
  nothing** — the slate is printed to the Actions log instead of Discord.
- The **persist step is guarded to `main`** (`if: github.ref_name == 'main'`),
  so a branch run **never writes to the `data` branch** and can't pollute the
  real track record.

So a branch run is safe: it reads live data and burns a little API credit, but
sends no alerts and leaves the track record alone.

---

## Notes & limits

- "Sharp" = on Polymarket's all-time profit leaderboard. Proven winners are often
  right, **not always** — take the contrarian flag seriously and size accordingly.
- The `/holders` and leaderboard data reflect Polymarket's **global** catalog;
  the US-regulated app can differ, so confirm in your app before betting.
- GitHub disables scheduled workflows after ~60 days of **no repo activity**.
  Each run force-pushes the track record to the `data` branch, which counts as
  activity — so an actively-running Moby keeps itself alive.
- **`main` is meant to be protected** (require a PR + passing CI). Because the
  log is persisted to the unprotected `data` branch with the default
  `GITHUB_TOKEN`, no ruleset bypass or personal access token is needed —
  automated commits never target `main`.
- Moby reads sentiment; it does not guarantee outcomes. Bet responsibly.

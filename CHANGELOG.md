# Changelog

All notable changes to **Moby** — the multi-factor smart-money sentiment agent
for Polymarket World Cup markets.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/). This
project isn't versioned, so entries are grouped by date / milestone. Earlier
history is reconstructed from memory and may be approximate.

---

## 2026-07-02

Two commits this day: `0ffd3de` (tags + first window model) and `a7bad03`
(coverage/window/contrarian fixes).

### Fixed
- **"No bets" while games remained today.** Upcoming games were surfacing no
  bettable props. Three independent root causes:
  - **Timestamp parsing.** Polymarket's `gameStartTime` is formatted
    `2026-07-03 03:00:00+00` (space separator, short `+00` offset), which
    `datetime.fromisoformat` rejected. `_parse_ts` silently fell back to the
    market's **creation** `startDate` (days earlier), so upcoming props looked
    long-finished and were dropped by the "skip finished games" grace filter.
    Now normalizes the format, and no longer uses `startDate` (creation) as a
    kickoff proxy — prefers `gameStartTime`, then `endDate`.
  - **Fetch cap.** Only the top 60 events by 24h volume were pulled; an upcoming
    game's prop events (`- More Markets`, `- Player Props`) rank lower and fell
    past the cutoff, so the game surfaced only its (unbettable-favorite)
    moneyline. Fetch now **paginates ~200 events** (`EVENT_FETCH_LIMIT`).
  - **Futures flooding.** Tournament futures leaked into the slate (47 selected
    at once). Futures are now marked distinctly and capped at `FUTURES_SLOTS`.
- **Window-boundary math.** The 5 PM cron fires at 16:20 CT; `next_scheduled_run`
  computed "next slot after now," saw 5 PM as still ahead, and shrank the 5 PM
  run's window to ~40 min — excluding the whole evening. It now keys off the
  **current run's slot**, so the 5 PM run correctly owns games until 7 AM (~14h).
- **Contrarian tag false positive.** On a longshot future (dollars sit on "No"
  by base rate), backing "Yes" was auto-tagged `contrarian` even though raw and
  sharp money both leaned Yes — the tag contradicted the rationale (the France
  winner future). The backstop now tags only a **genuine sharp-vs-crowd
  divergence** (sharp opposite raw *and* the pick follows sharp).

### Added
- **Hedge / contrarian tags** on picks (`tag` = none|contrarian|hedge, plus
  `tag_note`). Model-set, with a deterministic code backstop for the contrarian
  case. Rendered as a small badge in the card title + a "Role" line; conviction
  still drives the card color. Written to `signals_log.jsonl`.
- **`last_chance` window model.** Each run "owns" the games between now and the
  next scheduled run (Central 7 AM / 12 PM / 5 PM). New `next_scheduled_run()`.
  Markets carry `status` (live/upcoming/undated), `last_chance`, and
  minutes-to/since-kickoff.
- **Per-game diversity cap** (`MAX_GAME_PROPS_PER_GAME`, `MAX_PLAYER_PROPS_PER_GAME`)
  plus `_game_key()`, so one busy game (or a 200+ entry player-prop list) can't
  hog the slate and starve other games.
- **Novelty-market filter** — skips "what will the announcers say…" markets.
- **New tuning knobs:** `EVENT_FETCH_LIMIT` (200), `MARKET_CAP` (100),
  `MAX_GAME_PROPS_PER_GAME` (30), `MAX_PLAYER_PROPS_PER_GAME` (15),
  `WINDOW_HOURS` (18), `NEXT_RUN_BUFFER_MIN` (60), `LIVE_GRACE_MIN` (105).
- **CI regression tests** for the timestamp parser, window boundary, per-game
  diversity, novelty filter, divergence-only contrarian logic, and tag rendering.

### Changed
- **Coverage depth.** Each game's *full* standard market menu is now analyzed
  (per-game caps 8→30 game / 4→15 player; `MARKET_CAP` 60→100) — Moby picks the
  best rather than seeing a thin slice. (~$0.10–0.15/run on Haiku.)
- **Window policy.** Focus the current run's window (`last_chance` games) and
  surface each game's best ~2–4 bets; later-window games are usually saved for
  the run that owns them, but an *exceptional* standout may be grabbed early
  (loosened from an initial hard "never bet later games" rule).
- **Live games stay eligible longer.** `LIVE_GRACE_MIN` 75→105 min — 75 min of
  wall-clock since kickoff is only ~60 min played once halftime is counted, so
  live games with real time left were being dropped too early.
- Discord run header shows the slot (e.g. "🐋 Moby — 5:00 PM run") instead of
  "Today's slate."

---

## Earlier — reframe to "Moby" (exact dates not tracked)

### Changed / Reframed
- **Renamed** the whole project Poly / value_scout → **Moby** (script, workflow,
  README, log; repository renamed by the owner).
- **Removed the mispricing engine.** Dropped the sportsbook de-vig / arbitrage
  comparison entirely; replaced it with **multi-factor smart-money sentiment**
  read from Polymarket holder positioning.
- **Factor stack:** smart money (largest holders, dollar-weighted) → **sharp
  money** (re-weighted by each holder's all-time leaderboard PnL) → web-search
  news → self-graded track record → X/social feed (stubbed for later).
- **Daily slate** split into **game props → player props → futures**, match-level
  markets prioritized over tournament futures.
- Rewrote the README around the smart-money sentiment model.

### Added
- All-time **profitable-trader leaderboard** ("sharp money") weighting;
  divergence flagged when raw money and sharp money disagree.
- **Bet/signal tracking** (`signals_log.jsonl` with `condition_id`), self-graded
  win/loss on later runs and fed back to calibrate conviction (`load_track_record`).
- **Always sends a Discord message**, even on a no-bets run.
- **Color-coded Discord embeds** (conviction-based) with compact per-pick cards.
- **Detailed job-failure Discord alert** (separate workflow step).
- **CI smoke-test workflow** (compile + import + behavior checks on every push).
- **Per-run Anthropic cost logging** (`estimate_cost`).
- **Payoff focus** — price / profit-% / multiple per outcome; `prune_low_upside`
  backstop so a 100¢ / 0%-upside "lock" never ships.
- `run_slot_label()` — labels each run by its nearest Central slot.

### Fixed
- **JSON parse failure** — model exhausted its token budget on research before
  emitting JSON. `max_tokens` 4000→8000 + an explicit "the JSON block MUST
  appear" reminder.
- **Expensive run (~40¢).** Default model switched Sonnet → **Haiku**.
- **Discord empty-field crash** (HTTP 400) — added fallback values for empty
  embed fields.
- **Wrong Polymarket tag.** The `world-cup` tag holds only tournament futures;
  the actual per-match markets live under **`fifa-world-cup`** — switched, and
  refined market classification.
- **Player props misclassified** as game props because the event title contains
  " vs " — fixed the classification order (strong game phrases → player hints →
  bare " vs " moneyline → futures → other).
- **Futures dominated the slate** (money-size sort) — now sorts match-level
  (game → player) before futures.
- **Cards too long / `<cite>` tags** — brevity caps in the prompt + `_clean()`
  strips citation tags and truncates.
- **100¢ / 0%-upside "green" pick** — `prune_low_upside` + a prompt HARD RULE
  (never surface a pick priced ≥ 0.90 or = 1.0).
- **90th-minute game rehashed** instead of the upcoming match — introduced
  time-window tiers so nearly-finished games drop out.
- `commit_log` pathspec error when the log file didn't exist — existence guard.
- GitHub Actions Node 20 deprecation warning — updated action versions.

### Infrastructure
- Runs **3×/day on GitHub Actions**, pushing alerts to **Discord** (ntfy /
  Twilio as alternates).
- Cron set for US **Central** delivery (~7:20a / 12:20p / 5:20p CT), tuned early
  and off-the-hour to absorb GitHub's scheduler drift.
- Polymarket **Gamma** (events/markets) + **Data** (holders, leaderboard) APIs —
  free, no key.

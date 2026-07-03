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
- **Suggested stake in units** on every pick (1 unit = 1% of bankroll). Computed
  in code via **fractional Kelly** seeded by the pick's conviction (assumed edge)
  and price (odds) — `suggest_units` / `annotate_units`. Renders as a "Stake"
  card field; logged to `signals_log.jsonl`. Payoff-aware: sizes down longshots,
  up confident value, and suggests nothing with no positive edge. Knobs:
  `KELLY_FRACTION` (0.25), `MAX_UNITS` (5).
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

## 2026-06-29

The **Poly → Moby reframe** and its refinements. Commits `97a5384`, `7776eb9`,
`45ab0e4`, `c0eb003`, `bbadee3`, `8ae0656`, `a8205f2`, `e4b6969`, `52d56c2`.

### Changed / Reframed
- **Poly → Moby** (`97a5384`): replaced the sportsbook de-vig / mispricing engine
  with a `/holders`-based smart-money read. Added `fetch_holders` +
  `summarize_holders` (dollar-weighted lean per outcome). Renamed the script,
  workflow, Discord username, and log file (`signals_log.jsonl`).
- **Moby v2 — multi-factor daily slate** (`7776eb9`): picks grouped into game
  props / player props / futures. Added a graded track record
  (`fetch_market_resolution`, `load_track_record`), an X-sentiment stub
  (`fetch_x_sentiment`, `X_BEARER_TOKEN`-gated), and kept web search. Picks
  logged with `condition_id` for later grading; Discord shows a header card +
  one card per pick.
- **Sharp-money weighting** (`45ab0e4`): `fetch_sharp_traders` pulls the all-time
  SPORTS+OVERALL profit leaderboard (`/v1/leaderboard`); each holder weighted by
  lifetime PnL (`sharp_weight`). `summarize_holders` now emits
  `sharp_lean_side`/`pct` + `notable_sharps`; markets ranked by sharp-trader
  presence first; trust the sharp side on divergence. Full README rewrite.
- **Match-level first + concise cards** (`8ae0656`): match markets prioritized
  over futures; compact card layout with brevity caps.
- **Payoff prioritization** (`bbadee3`): avoid trivial-upside favorites; surface
  price / payout per pick.

### Added
- **Slot-labeled runs, time-window prioritization, zero-upside guard**
  (`a8205f2`): Discord header shows "X:00 run" (nearest Central slot);
  `clean_markets` prioritizes upcoming games (soonest first) and drops games
  kicked off >75 min ago; `run_context` + window passed to the model;
  `prune_low_upside()` hard guard so a pick priced ≥0.90 or =1.0 never ships.
- **CI coverage** for `run_slot_label` and `prune_low_upside` (`e4b6969`).
- **Live games stay eligible** when not near the end (`52d56c2`) — first pass at
  the grace window (later tuned to 105 min on 2026-07-02).

### Fixed
- **Wrong Polymarket tag** (`c0eb003`): scan `fifa-world-cup` (has the live
  per-match markets), not `world-cup` (tournament futures only).

---

## 2026-06-28

Initial build and the **Poly-era** feature growth (commits `a7f931a` → `3d26934`).

### Added
- **Initial Polymarket Value Scout** (`a7f931a`) — the original sportsbook-vs-
  Polymarket mispricing scanner.
- **US Central cron** (`197ac15`); later shifted ~1h10m earlier and off-the-hour
  (`:20`) to absorb GitHub scheduler drift (`be26667`).
- **Always send a Discord message**, even with no bets (`c400e17`).
- **Analytical value bets**, not just sportsbook price mismatches (`e050b14`).
- **Discord embeds** with color coding + a bet tracking log (`18cbff7`); hardened
  against empty field values and length limits (`939c7c7`).
- **Job-failure Discord alert** (`4edb507`), later made detailed — repo, run #,
  trigger, branch, commit, time, likely causes (`0932f9f`).
- **Renamed to Poly** with richer Discord alerts — sources, near misses, stake
  guide, scan count (`b65e46d`).
- **CI smoke test** on every push — compile, import, JSON parse, Discord payload
  safety (`8ae729d`).
- **Per-run cost logging** from API usage — tokens + web searches (`afad097`).
- **Type-based market prioritization** — game props → player props → futures, not
  just volume (`29538fd`); upcoming games first + a small reserved futures slot +
  game/player classification-order fix (`3d26934`).

### Changed
- **max_tokens → 8000** + a JSON reminder to stop truncated output (`f78e9aa`).
- **Switched to Haiku** and cut web-search uses to reduce cost (`ef62a5d`).
- **Relaxed constraints** to surface ~2-3 bets/day — 30 events, 40-market cap,
  looser liquidity/spread, tiered-confidence prompt (`eb0c03b`); then **widened
  coverage** to all World Cup markets incl. game props — 60 events, 60-market
  cap, lower liquidity floor, 12 searches (`f2d6d36`).

### Fixed
- **Node 20 deprecation** — bumped `checkout@v5` / `setup-python@v6` (`23618a5`).
- **CI referenced a removed `build_sms`** — check `send_alert` instead (`27aa039`).
- **`commit_log` guard** — skip when no log file exists; only push on a real
  commit (`6ed686c`).

---

## Infrastructure (throughout)

- Runs **3×/day on GitHub Actions**, pushing alerts to **Discord** (ntfy / Twilio
  as alternates). Cron is UTC, tuned early + off-the-hour for drift.
- Polymarket **Gamma** (events/markets) + **Data** (holders, leaderboard) APIs —
  free, no key.
- Scheduled runs also produce frequent `chore: log smart-money signals` commits
  (the bot persisting `signals_log.jsonl` for later grading) — omitted here.

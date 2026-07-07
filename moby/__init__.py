"""
Moby — Polymarket smart-money sentiment agent (cloud edition).

Runs on a schedule (e.g. GitHub Actions cron), with NO dependency on a local
machine being awake. Each run:

  1. Pulls live markets for a tag (default 2026 FIFA World Cup) from Polymarket's
     public Gamma API.
  2. For each market, pulls the LARGEST holders on each outcome from Polymarket's
     public Data API (/holders) — i.e. where the biggest money / P&L is sitting.
  3. Asks Claude ("Moby") to read smart-money SENTIMENT from that positioning:
     which side the big money leans, how concentrated/lopsided it is, and how
     much conviction to assign.
  4. Pushes the strongest smart-money signals to your phone via a Discord webhook
     (or ntfy.sh / Twilio). Stays useful even on quiet runs.

This is an informational research tool, not financial advice, and it never
places bets. You confirm price/availability in your Polymarket app and bet
responsibly yourself.

Required environment variables (set as GitHub Actions secrets):
  ANTHROPIC_API_KEY     - your Anthropic API key

Alert channel — set ONE of these (checked in this order). All are free except
Twilio:
  DISCORD_WEBHOOK_URL   - a Discord channel webhook URL (recommended). Also the
                          fallback + ops/failure channel for every sport.
  DISCORD_WEBHOOK_URL_<SPORT> - per-sport channel webhook (e.g. _WNBA); falls
                          back to DISCORD_WEBHOOK_URL when unset/empty.
  NTFY_TOPIC            - an ntfy.sh topic name (free, no signup).
  TWILIO_* / ALERT_TO_PHONE - real SMS via Twilio (paid).

Optional:
  MOBY_SPORTS           - default "soccer" (comma-separated sport keys,
                          e.g. "soccer,wnba"; unknown key = startup error)
  MODEL_SYNTH           - default "claude-sonnet-4-6" (Stage C synthesis)
  MODEL_NEWS            - default "claude-haiku-4-5-20251001" (Stage B brief)
  ANTHROPIC_MODEL       - legacy synthesis-model override, honored if set
  BATCH_MODE            - default "1" (Stage C rides a Messages Batch, 50% off;
                          "0" forces direct calls)
  BATCH_WAIT_MIN        - default 20 (batch poll cap in minutes, then cancel +
                          per-sport direct fallback)
  PREFILTER_TOP_N       - default 30 (markets kept in the model view per sport)
  NEWS_MAX_SEARCHES     - default 5 (web searches per news brief)
  MARKET_TAG            - overrides the active sport profile's Gamma tag_slug
  EVENT_FETCH_LIMIT     - default 200 (events pulled from Gamma, paginated)
  MARKET_CAP            - default 100 (markets analyzed per run)
  FUTURES_SLOTS         - default 4 (slots reserved for futures markets)
  MAX_GAME_PROPS_PER_GAME   - default 30 (per-game cap; ~full menu, tail trimmed)
  MAX_PLAYER_PROPS_PER_GAME - default 15 (per-game player-prop cap)
  WINDOW_HOURS          - default 18 (outer reach of a run's slate)
  NEXT_RUN_BUFFER_MIN   - default 60 (grace past the next run for "last chance")
  LIVE_GRACE_MIN        - default 105 (drop live games kicked off > this ago)
  MIN_LIQUIDITY         - default 500
  MAX_SPREAD            - default 0.07
  MIN_SMART_MONEY_USD   - default 2000 (skip markets with little big-money interest)
  KELLY_FRACTION        - default 0.25 (fraction of full Kelly for unit sizing)
  MAX_UNITS             - default 5 (cap on suggested stake; 1 unit = 1% bankroll)
  DRY_RUN               - "1" to skip sending the alert (prints instead)

This package shadows the moby.py shim on import; it re-exports the full public
surface so `import moby; moby.clean_markets(...)` keeps working exactly as it
did when everything lived in one file.
"""
from moby.alerts import send_alert
from moby.factors import fetch_x_sentiment, load_track_record
from moby.llm import (
    MODEL_PRICING,
    WEB_SEARCH_COST,
    build_synthesis_user,
    estimate_cost,
    parse_json_block,
    resolve_models,
    run_analysis,
    run_news_brief,
    run_synthesis,
    wants_news_brief,
)
from moby.markets import (
    _FUTURE_HINTS,
    _GAME_STRONG,
    _NOVELTY,
    _PLAYER_HINTS,
    _game_key,
    classify_market,
    clean_markets,
    payouts_for,
)
from moby.picks import (
    BUCKETS,
    _BUCKET_TO_TYPE,
    _opposes_raw_lean,
    _side_matches,
    annotate_contrarian,
    annotate_units,
    flatten_picks,
    prune_low_upside,
    suggest_units,
)
from moby.pipeline import main, run_sport
from moby.prefilter import compact_market, prefilter_markets
from moby.polymarket import (
    DATA_BASE,
    GAMMA_BASE,
    USER_AGENT,
    _FAR_FUTURE,
    _as_list,
    _parse_ts,
    _to_float,
    fetch_events,
    fetch_holders,
    fetch_market_resolution,
    fetch_sharp_traders,
)
from moby.prompts import ANALYSIS_INSTRUCTIONS, render_instructions
from moby.render import (
    CONF_COLOR,
    TAG_BADGE,
    TAG_ROLE,
    _BUCKET_LABEL,
    _clean,
    _fmt_list,
    build_discord_payload,
)
from moby.smartmoney import attach_smart_money, sharp_weight, summarize_holders
from moby.sports import SPORTS, get_profiles
from moby.sports.base import SportProfile
from moby.tracklog import log_signals
from moby.windows import next_scheduled_run, run_slot_label

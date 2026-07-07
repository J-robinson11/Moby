"""Run orchestration — run_sport(profile) is the end-to-end per-sport pipeline;
main() runs it for every active sport in the registry."""
import json
import os
from datetime import datetime, timezone

from anthropic import Anthropic

from moby.alerts import send_alert
from moby.config import knob
from moby.factors import fetch_x_sentiment, load_track_record
from moby.llm import (
    build_synthesis_user,
    resolve_models,
    run_news_brief,
    run_synthesis,
    wants_news_brief,
)
from moby.markets import clean_markets
from moby.picks import (
    BUCKETS,
    annotate_contrarian,
    annotate_units,
    flatten_picks,
    prune_low_upside,
)
from moby.polymarket import fetch_events
from moby.prefilter import prefilter_markets
from moby.render import build_discord_payload
from moby.smartmoney import attach_smart_money
from moby.sports import get_profiles
from moby.tracklog import commit_log, log_signals
from moby.windows import next_scheduled_run, run_slot_label


def run_sport(profile) -> int:
    tag = os.environ.get("MARKET_TAG") or profile.market_tag
    min_liquidity = float(knob("MIN_LIQUIDITY", "500", profile))
    max_spread = float(knob("MAX_SPREAD", "0.07", profile))
    min_smart_usd = float(knob("MIN_SMART_MONEY_USD", "2000", profile))
    model_synth, model_news = resolve_models()
    dry_run = os.environ.get("DRY_RUN") == "1"

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    slot = run_slot_label(now_dt)
    window_hours = float(knob("WINDOW_HOURS", "18", profile))
    print(f"[{now}] Moby run | sport={profile.key} slot={slot} tag={tag} "
          f"synth={model_synth} news={model_news}")

    events = fetch_events(tag)
    markets = clean_markets(events, min_liquidity, max_spread, profile)
    print(f"Candidate markets: {len(markets)}")
    if not markets:
        print("No candidate markets this run. Exiting quietly.")
        return 0

    markets = attach_smart_money(markets, min_smart_usd)
    print(f"Markets with smart-money interest (>= ${min_smart_usd:.0f}): {len(markets)}")
    if not markets:
        print("No markets cleared the smart-money threshold. Exiting quietly.")
        return 0

    # Build market -> condition_id map for logging/grading before the model view.
    cid_by_market = {m["question"]: m.get("condition_id", "") for m in markets}

    # Extra sentiment factors.
    track_record = load_track_record()
    x_sentiment = fetch_x_sentiment(markets)
    print("Track record:", track_record.get("note", ""))
    print("X sentiment:", x_sentiment.get("note", ""))

    next_run_label = next_scheduled_run(now_dt)[1]
    run_context = {
        "now_utc": now,
        "run_label": f"{slot} CT",
        "next_run": f"{next_run_label} CT",
        "window_hours": window_hours,
        "note": (f"Runs happen ~3x/day; the NEXT run is {next_run_label} CT. Focus "
                 "on last_chance=true games (live with time left, or kicking off "
                 "before the next run) — surface each game's best ~2-4 bets from "
                 "its full market menu. last_chance=false games are usually saved "
                 "for the later run that owns them; include one only if truly "
                 "exceptional. Few or no bets is fine if this window has nothing "
                 "bettable."),
    }

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Stage A ($0): curate + compact the model's view.
    curated = prefilter_markets(markets, profile)
    print(f"Stage A prefilter: {len(markets)} -> {len(curated)} markets in the model view")

    # Stage B (Haiku + search): only when this window actually owns games.
    if wants_news_brief(markets):
        news_brief = run_news_brief(client, model_news, profile, curated, run_context)
    else:
        news_brief = {"status": "skipped",
                      "note": "No last-chance games in this window; news search not run."}
        print("Stage B news brief skipped: no last-chance games this window.")

    # Stage C (Sonnet, batch with direct fallback): no tools, curated input.
    user = build_synthesis_user(profile, curated, news_brief, track_record,
                                x_sentiment, run_context)
    result = run_synthesis(client, {profile.key: {"profile": profile, "user": user}})[profile.key]
    result["markets_evaluated"] = len(markets)
    result["_track_record"] = track_record
    result["_run_slot"] = slot

    # Hard backstop: drop zero/low-upside picks (e.g. a 100¢ lock) the model
    # shouldn't have surfaced, regardless of how it labeled them.
    max_price = float(os.environ.get("MAX_PICK_PRICE", "0.90"))
    pruned = prune_low_upside(result, max_price=max_price)
    if pruned:
        print(f"Pruned {pruned} low/zero-upside pick(s) priced >= {max_price} or <= 0.05.")

    # Flag picks that go against the raw big-money crowd as 'contrarian'
    # (backstop; the model already tags hedges + contrarians itself). Uses the
    # holder data we already computed, so it's free.
    lean_by_market = {
        m["question"]: {
            "lean_side": (m.get("smart_money") or {}).get("lean_side"),
            "sharp_lean_side": (m.get("smart_money") or {}).get("sharp_lean_side"),
            "sharp_present": (m.get("smart_money") or {}).get("sharp_traders_present", 0),
            "outcomes": m.get("outcomes"),
        }
        for m in markets
    }
    auto_tagged = annotate_contrarian(result, lean_by_market)
    if auto_tagged:
        print(f"Auto-tagged {auto_tagged} pick(s) 'contrarian' (oppose raw-money lean).")

    # Suggested stake per pick, in units (fractional Kelly from conviction+price).
    staked = annotate_units(result)
    if staked:
        print(f"Sized {staked} pick(s) with a suggested unit stake.")

    print("Summary:", result.get("summary", ""))
    print("Watchlist:", result.get("watchlist", []))
    picks = flatten_picks(result)
    print(f"Picks: {len(picks)} "
          f"({', '.join(b + '=' + str(sum(1 for p in picks if p['bucket'] == b)) for b in BUCKETS)})")
    print(json.dumps(result, indent=2))

    log_signals(result, now, cid_by_market)
    commit_log()

    if dry_run:
        print("DRY_RUN=1, would have alerted:")
        print(json.dumps(build_discord_payload(result), indent=2))
    else:
        send_alert(result)
    return 0


def main() -> int:
    """Run every active sport (MOBY_SPORTS, default 'soccer').

    Phase 4 turns this into the fault-isolated multi-sport loop with one
    shared synthesis batch; until then the registry holds only soccer, so
    behavior is identical to the single-sport script.
    """
    rc = 0
    for profile in get_profiles():
        rc = max(rc, run_sport(profile))
    return rc

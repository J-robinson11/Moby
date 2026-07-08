"""Run orchestration — the fault-isolated multi-sport flow.

Each sport is prepared independently (prepare_sport), every prepared sport
rides ONE shared synthesis batch (run_synthesis), then each is finished and
alerted independently (finish_sport). A single sport's exception is isolated so
it can't kill its siblings; main() returns non-zero if ANY sport failed.
run_sport(profile) stays as a thin single-sport wrapper for the legacy surface.
"""
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
    enforce_tag_budget,
    flatten_picks,
    prune_low_upside,
)
from moby.polymarket import fetch_events
from moby.prefilter import prefilter_markets
from moby.render import build_discord_payload
from moby.smartmoney import attach_smart_money
from moby.sports import get_profiles
from moby.tracklog import log_signals
from moby.windows import next_scheduled_run, run_slot_label


def has_game_window(markets: list, window_hours: float) -> bool:
    """The season gate: True only if some game/player market is LIVE or starts
    within the window. Futures/speculation markets exist year-round (NFL win
    totals in July, "next team" markets), so "any candidate markets" isn't
    enough to tell an in-season sport from a dark one — a dark sport must cost
    $0 (no holder fetches, no model call) and post nothing."""
    window_min = window_hours * 60
    for m in markets:
        if m.get("market_type") not in ("game_prop", "player_prop"):
            continue
        if m.get("status") == "live":
            return True
        if (m.get("status") == "upcoming"
                and m.get("mins_to_kickoff", float("inf")) <= window_min):
            return True
    return False


def prepare_sport(client, profile) -> dict | None:
    """Everything up to (and including) the Stage-C user message for one sport.

    Runs the $0/cheap stages — fetch, clean, smart-money attach, factors, Stage
    A prefilter, Stage B news brief — and returns the prep dict finish_sport
    needs. Returns None on a quiet exit (no candidate markets, or none clear the
    smart-money threshold) — a quiet exit is NOT a failure. The expensive Stage
    C synthesis is deliberately left out so every sport can share ONE batch.
    """
    tag = os.environ.get("MARKET_TAG") or profile.market_tag
    min_liquidity = float(knob("MIN_LIQUIDITY", "500", profile))
    max_spread = float(knob("MAX_SPREAD", "0.07", profile))
    min_smart_usd = float(knob("MIN_SMART_MONEY_USD", "2000", profile))
    model_synth, model_news = resolve_models()

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    slot = run_slot_label(now_dt)
    window_hours = float(knob("WINDOW_HOURS", "18", profile))
    print(f"[{now}] Moby run | sport={profile.key} slot={slot} tag={tag} "
          f"synth={model_synth} news={model_news}")

    events = fetch_events(tag)
    markets = clean_markets(events, min_liquidity, max_spread, profile)
    print(f"[{profile.key}] Candidate markets: {len(markets)}")
    if not markets:
        print(f"[{profile.key}] No candidate markets this run. Exiting quietly.")
        return None

    # Season gate — before attach_smart_money, so a dark sport skips the ~100
    # /holders calls too, not just the model. REQUIRE_GAME_WINDOW=0 disables.
    if (knob("REQUIRE_GAME_WINDOW", "1", profile) != "0"
            and not has_game_window(markets, window_hours)):
        print(f"[{profile.key}] No live/upcoming games within {window_hours:.0f}h "
              "(off-season or dark week). Exiting quietly.")
        return None

    markets = attach_smart_money(markets, min_smart_usd)
    print(f"[{profile.key}] Markets with smart-money interest (>= ${min_smart_usd:.0f}): {len(markets)}")
    if not markets:
        print(f"[{profile.key}] No markets cleared the smart-money threshold. Exiting quietly.")
        return None

    # Build market -> condition_id map for logging/grading before the model view.
    cid_by_market = {m["question"]: m.get("condition_id", "") for m in markets}

    # Extra sentiment factors — track record scoped to THIS sport's rows.
    track_record = load_track_record(sport=profile.key)
    x_sentiment = fetch_x_sentiment(markets)
    print(f"[{profile.key}] Track record:", track_record.get("note", ""))
    print(f"[{profile.key}] X sentiment:", x_sentiment.get("note", ""))

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

    # Stage A ($0): curate + compact the model's view.
    curated = prefilter_markets(markets, profile)
    print(f"[{profile.key}] Stage A prefilter: {len(markets)} -> {len(curated)} markets in the model view")

    # Stage B (Haiku + search): only when this window actually owns games.
    if wants_news_brief(markets):
        news_brief = run_news_brief(client, model_news, profile, curated, run_context)
    else:
        news_brief = {"status": "skipped",
                      "note": "No last-chance games in this window; news search not run."}
        print(f"[{profile.key}] Stage B news brief skipped: no last-chance games this window.")

    # Stage C user message — the batch consumes this; synthesis runs in main().
    user = build_synthesis_user(profile, curated, news_brief, track_record,
                                x_sentiment, run_context)
    return {
        "profile": profile,
        "user": user,
        "markets": markets,
        "cid_by_market": cid_by_market,
        "track_record": track_record,
        "slot": slot,
        "now": now,
        # Stage B spend, carried forward so finish_sport can report the true
        # per-sport total (the result's _cost only covers Stage C synthesis).
        "news_cost": float((news_brief.get("_cost") or {}).get("total_cost", 0.0)),
    }


def finish_sport(prep: dict, result: dict) -> None:
    """Stage D for one sport: annotate the synthesis result, log it, alert it.

    Takes the prep dict from prepare_sport and this sport's parsed synthesis
    result; mutates result with the render/log metadata (incl. the new
    _sport_label for the multi-sport Discord header), prunes/tags/sizes picks,
    logs the signals under this sport, and sends the alert to the sport's
    channel (or prints under DRY_RUN)."""
    profile = prep["profile"]
    markets = prep["markets"]
    cid_by_market = prep["cid_by_market"]
    dry_run = os.environ.get("DRY_RUN") == "1"
    test_run = os.environ.get("TEST_RUN") == "1"

    result["markets_evaluated"] = len(markets)
    result["_track_record"] = prep["track_record"]
    result["_run_slot"] = prep["slot"]
    result["_sport_label"] = profile.label
    if test_run:
        result["_test_run"] = True  # 🧪 TEST badge on the Discord header

    # Hard backstop: drop zero/low-upside picks (e.g. a 100¢ lock) the model
    # shouldn't have surfaced, regardless of how it labeled them.
    max_price = float(os.environ.get("MAX_PICK_PRICE", "0.90"))
    pruned = prune_low_upside(result, max_price=max_price)
    if pruned:
        print(f"[{profile.key}] Pruned {pruned} low/zero-upside pick(s) priced >= {max_price} or <= 0.05.")

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
        print(f"[{profile.key}] Auto-tagged {auto_tagged} pick(s) 'contrarian' (oppose raw-money lean).")

    # Tag budget: max ONE hedge + ONE contrarian per slate, and a hedge must
    # genuinely oppose another pick — surplus/mislabeled ones are dropped.
    tag_dropped = enforce_tag_budget(result)
    if tag_dropped:
        print(f"[{profile.key}] Tag budget: dropped {tag_dropped} surplus/invalid hedge-or-contrarian pick(s).")

    # Suggested stake per pick, in units (fractional Kelly from conviction+price).
    staked = annotate_units(result)
    if staked:
        print(f"[{profile.key}] Sized {staked} pick(s) with a suggested unit stake.")

    # The one-line spend summary the single-file engine used to print — the
    # staged engine's per-stage lines don't add up for you, so this does.
    news_cost = float(prep.get("news_cost", 0.0))
    synth_cost = float((result.get("_cost") or {}).get("total_cost", 0.0))
    result["_cost_run_total"] = round(news_cost + synth_cost, 4)
    print(f"[{profile.key}] Cost: ${result['_cost_run_total']:.4f} this sport "
          f"(news ${news_cost:.4f} + synthesis ${synth_cost:.4f})")

    print(f"[{profile.key}] Summary:", result.get("summary", ""))
    print(f"[{profile.key}] Watchlist:", result.get("watchlist", []))
    picks = flatten_picks(result)
    print(f"[{profile.key}] Picks: {len(picks)} "
          f"({', '.join(b + '=' + str(sum(1 for p in picks if p['bucket'] == b)) for b in BUCKETS)})")
    print(json.dumps(result, indent=2))

    if test_run:
        # A test slate must never enter the track record it would later grade.
        print(f"[{profile.key}] TEST_RUN=1 — signals not logged.")
    else:
        log_signals(result, prep["now"], cid_by_market, sport=profile.key)

    if dry_run:
        print(f"[{profile.key}] DRY_RUN=1, would have alerted:")
        print(json.dumps(build_discord_payload(result), indent=2))
    else:
        send_alert(result, profile)


def run_sport(profile) -> int:
    """Single-sport end-to-end (legacy surface). prepare → synthesis → finish;
    a quiet prepare (None) exits 0."""
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    prep = prepare_sport(client, profile)
    if prep is None:
        return 0
    jobs = {profile.key: {"profile": profile, "user": prep["user"]}}
    result = run_synthesis(client, jobs)[profile.key]
    finish_sport(prep, result)
    return 0


def main() -> int:
    """Run every active sport (MOBY_SPORTS, default 'soccer') with fault
    isolation and ONE shared synthesis batch.

    A sport's exception during prepare or finish is caught and logged so it
    can't kill its siblings; a quiet exit (None from prepare) is not a failure.
    Returns 1 if ANY sport failed, else 0.
    """
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    failed = False

    # Phase 1: prepare every sport independently (cheap stages, fault-isolated).
    preps = {}
    for profile in get_profiles():
        try:
            prep = prepare_sport(client, profile)
        except Exception as exc:  # noqa: BLE001 — one sport must not sink the rest
            print(f"[{profile.key}] sport failed: {exc}")
            failed = True
            continue
        if prep is not None:  # None = quiet exit, not a failure
            preps[profile.key] = prep

    # Phase 2: ONE synthesis batch for every prepared sport.
    if preps:
        jobs = {key: {"profile": prep["profile"], "user": prep["user"]}
                for key, prep in preps.items()}
        results = run_synthesis(client, jobs)

        # Phase 3: finish + alert each sport independently (fault-isolated).
        run_total = 0.0
        for key, prep in preps.items():
            try:
                finish_sport(prep, results[key])
                run_total += results[key].get("_cost_run_total", 0.0)
            except Exception as exc:  # noqa: BLE001
                print(f"[{key}] sport failed: {exc}")
                failed = True
        print(f"Run cost, all sports: ${round(run_total, 4):.4f}")

    return 1 if failed else 0

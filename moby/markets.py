"""Market classification, cleaning, and slate selection.

Classification hints come from a SportProfile; without one, the soccer hints
apply (they are the original single-file tuples, now living in
moby/sports/soccer.py) so the legacy `moby.classify_market(q, ev)` surface
behaves exactly as before.
"""
from datetime import datetime, timezone

from moby.config import knob
from moby.polymarket import _FAR_FUTURE, _as_list, _parse_ts, _to_float
from moby.sports.soccer import (
    FUTURE_HINTS as _FUTURE_HINTS,
    GAME_STRONG as _GAME_STRONG,
    NOVELTY as _NOVELTY,
    PLAYER_HINTS as _PLAYER_HINTS,
)
from moby.windows import next_scheduled_run


def classify_market(question: str, event: str, profile=None) -> tuple:
    """Return (priority, label). Lower priority is scanned/ranked first.

    Order: specific match-market phrase -> player signal -> bare 'X vs Y'
    moneyline -> tournament/futures -> other.
    """
    if profile is not None and profile.classify is not None:
        return profile.classify(question, event)
    game_strong = profile.game_strong if profile else _GAME_STRONG
    player_hints = profile.player_hints if profile else _PLAYER_HINTS
    future_hints = profile.future_hints if profile else _FUTURE_HINTS
    q = question.lower()
    ev = event.lower()
    text = f"{q} {ev}"
    if any(h in text for h in game_strong):
        return (0, "game_prop")
    if any(h in text for h in player_hints):
        return (1, "player_prop")
    if " vs " in ev or " vs." in ev or " v " in ev or " vs " in q:
        return (0, "game_prop")  # bare match moneyline / per-match market
    if any(h in text for h in future_hints):
        return (2, "future")
    return (3, "other")


def payouts_for(outcomes: list, prices: list) -> dict:
    """For each outcome, the back price and the upside if it wins.

    profit_pct = (1 - price) / price * 100  → return per $1 staked.
    A 0.90 favorite returns ~11%; a 0.40 pick returns ~150%.
    """
    out = {}
    for name, p in zip(outcomes, prices):
        if p and p > 0:
            out[name] = {
                "price": round(p, 3),
                "profit_pct": round((1 - p) / p * 100),
                "multiple": round(1 / p, 2),
            }
    return out


def _game_key(event_title: str) -> str:
    """Collapse a single match's several events into one key so per-game caps
    span all of them: 'Brazil vs. Japan - More Markets', '... - Player Props'
    and '... - Exact Score' all map to 'Brazil vs. Japan'."""
    t = str(event_title or "")
    return t.split(" - ")[0].strip() or t


def clean_markets(events: list, min_liquidity: float, max_spread: float,
                  profile=None) -> list:
    """Flatten events -> markets; keep liquid, tight-spread ones; prioritize."""
    novelty = profile.novelty if profile else _NOVELTY
    game_key = (profile.game_key if profile and profile.game_key else _game_key)
    cleaned = []
    for ev in events:
        ev_title = ev.get("title", "")
        for m in ev.get("markets", []) or []:
            if m.get("closed") or not m.get("active", True):
                continue
            if any(n in (ev_title + " " + (m.get("question") or "")).lower() for n in novelty):
                continue  # skip novelty markets ("what will the announcers say...")
            liquidity = _to_float(m.get("liquidity"))
            spread = _to_float(m.get("spread"), default=1.0)
            if liquidity < min_liquidity or spread > max_spread:
                continue
            outcomes = _as_list(m.get("outcomes"))
            prices = [_to_float(p) for p in _as_list(m.get("outcomePrices"))]
            if not outcomes or len(outcomes) != len(prices):
                continue
            condition_id = m.get("conditionId") or m.get("condition_id") or ""
            if not condition_id:
                continue  # can't fetch holders without it
            question = m.get("question", "")
            priority, label = classify_market(question, ev_title, profile)
            # Prefer the real kickoff; fall back to the market/event END (≈ game
            # window). Deliberately NOT startDate — that's the market's creation
            # date (often days before kickoff), which would make an upcoming game
            # look long-finished and get grace-dropped.
            ts = _parse_ts(
                m.get("gameStartTime"), m.get("endDate"), ev.get("endDate"),
            )
            cleaned.append(
                {
                    "event": ev_title,
                    "question": question,
                    "market_type": label,
                    "condition_id": condition_id,
                    "starts": m.get("gameStartTime") or m.get("startDate")
                    or ev.get("startDate") or m.get("endDate") or "",
                    "_priority": priority,
                    "_ts": ts,
                    "outcomes": outcomes,
                    "implied_prob": prices,  # 0-1, Polymarket mid
                    "payout_by_outcome": payouts_for(outcomes, prices),
                    "volume24hr": _to_float(m.get("volume24hr")),
                    "liquidity": liquidity,
                }
            )

    cap = int(knob("MARKET_CAP", "100", profile))
    futures_slots = int(knob("FUTURES_SLOTS", "4", profile))
    futures_slots = max(0, min(futures_slots, cap))

    # --- Time window keyed to the NEXT scheduled run. Any game that kicks off
    # (or is live with time left) BEFORE the next run is "last chance" — this run
    # is its only shot at a Moby bet, so it's top priority. Games after the next
    # run can wait; the next run will cover them. Live games are dropped only once
    # finished / in the final stretch (wall-clock since kickoff ≈ mins played +
    # 15min halftime, so ~75min played ≈ ~90min wall-clock — that's the cutoff).
    now_dt = datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    grace_default = str(profile.live_grace_min) if profile else "105"
    grace = float(knob("LIVE_GRACE_MIN", grace_default, profile)) * 60  # drop games kicked off > this ago (~75min played)
    window = float(knob("WINDOW_HOURS", "18", profile)) * 3600          # outer reach of the slate at all
    buffer = float(knob("NEXT_RUN_BUFFER_MIN", "60", profile)) * 60     # grace past the next run (absorbs scheduler drift)
    last_chance_until = next_scheduled_run(now_dt)[0] + buffer        # bet-now-or-never boundary
    for m in cleaned:
        if m["_priority"] == 2:                # tournament future, not a timed match
            m["status"] = "future"
            m["last_chance"] = False
            m["_ttk"] = None
            continue
        ttk = (m["_ts"] - now_ts) if m["_ts"] != _FAR_FUTURE else None  # seconds to kickoff
        m["_ttk"] = ttk
        if ttk is None:
            m["status"] = "undated"
            m["last_chance"] = False
        elif ttk < 0:
            m["status"] = "live"
            m["mins_since_kickoff"] = round(-ttk / 60)
            m["last_chance"] = True                          # live w/ time left = only chance now
        else:
            m["status"] = "upcoming"
            m["mins_to_kickoff"] = round(ttk / 60)
            m["last_chance"] = m["_ts"] <= last_chance_until  # kicks off before the next run

    def prop_key(m):
        """Tier 0 = last chance (live w/ time left OR kicks off before the next
        run), 1 = later (the next run will cover it), 2 = far, 3 = undated.
        Within a tier: game props before player props, sooner before later."""
        ttk = m["_ttk"]
        if ttk is None:
            return (3, m["_priority"], 0)
        if ttk < 0:
            return (0, m["_priority"], -ttk)      # live, time left → last chance
        if m["_ts"] <= last_chance_until:
            return (0, m["_priority"], ttk)       # before next run → last chance
        if ttk <= window:
            return (1, m["_priority"], ttk)       # after next run → next run covers it
        return (2, m["_priority"], ttk)           # far off

    # Exclude only finished / final-stretch props (kicked off more than grace ago).
    props = [m for m in cleaned
             if m["_priority"] in (0, 1, 3)
             and not (m["_ttk"] is not None and m["_ttk"] < -grace)]
    futures = [m for m in cleaned if m["_priority"] == 2]
    props.sort(key=prop_key)
    futures.sort(key=lambda x: (x["_ts"], -x["volume24hr"]))

    # Diversity guard (generous): each game contributes up to its FULL standard
    # menu of markets, so the model sees ~all the real bet types and picks the
    # best — while still capping the pathological tail (a 200+ entry player-prop
    # list, every corner/exact-score line) so one game can't crowd the others out
    # entirely. Game and player props are capped separately per game; props is
    # priority-sorted, so each game keeps its strongest markets first and the
    # excess is filler used only if slots remain.
    max_g = int(knob("MAX_GAME_PROPS_PER_GAME", "30", profile))
    max_p = int(knob("MAX_PLAYER_PROPS_PER_GAME", "15", profile))
    counts, primary, overflow = {}, [], []
    for m in props:
        c = counts.setdefault(game_key(m.get("event", "")), [0, 0])
        slot_i = 1 if m["_priority"] == 1 else 0          # player props vs game/other
        if c[slot_i] < (max_p if slot_i else max_g):
            c[slot_i] += 1
            primary.append(m)
        else:
            overflow.append(m)
    props = primary + overflow

    props_slots = cap - futures_slots
    selected = props[:props_slots] + futures[:futures_slots]
    if len(selected) < cap:
        chosen = {id(m) for m in selected}
        leftovers = [m for m in props[props_slots:] + futures[futures_slots:]
                     if id(m) not in chosen]
        selected += leftovers[: cap - len(selected)]

    for m in selected:
        m.pop("_priority", None)
        m.pop("_ts", None)
        m.pop("_ttk", None)
    return selected

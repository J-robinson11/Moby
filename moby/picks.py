"""Pick post-processing: buckets, pruning, contrarian backstop, unit sizing."""
import os

from moby.polymarket import _to_float

BUCKETS = ("game_props", "player_props", "futures")
_BUCKET_TO_TYPE = {"game_props": "game_prop", "player_props": "player_prop", "futures": "future"}


def flatten_picks(result: dict) -> list:
    """Flatten result['picks'] into a single list, tagging each with its bucket."""
    picks = result.get("picks", {}) or {}
    out = []
    for bucket in BUCKETS:
        for p in picks.get(bucket, []) or []:
            out.append({**p, "bucket": bucket, "market_type": _BUCKET_TO_TYPE[bucket]})
    return out


def prune_low_upside(result: dict, max_price: float = 0.90, min_price: float = 0.05) -> int:
    """Drop picks with no real upside (priced >= max_price, e.g. a 100¢ lock) or
    pure longshots (<= min_price). Hard backstop so a 0%-payout pick never ships."""
    picks = result.get("picks", {}) or {}
    removed = 0
    for b in BUCKETS:
        kept = []
        for p in picks.get(b, []) or []:
            try:
                pr = float(p.get("price"))
            except (TypeError, ValueError):
                pr = None
            if pr is not None and (pr >= max_price or pr <= min_price):
                removed += 1
                continue
            kept.append(p)
        picks[b] = kept
    result["picks"] = picks
    return removed


def _side_matches(a, b) -> bool:
    """Loose match between a model's pick string and an outcome label."""
    a = str(a or "").strip().lower()
    b = str(b or "").strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _opposes_raw_lean(pick_side: str, lean_side: str, outcomes) -> bool:
    """True if the pick clearly backs a DIFFERENT outcome than the raw-money
    lean (a contrarian-to-the-crowd play). Conservative: only fires when the
    pick positively matches a non-lean outcome, so it can't mis-flag."""
    if not lean_side or _side_matches(pick_side, lean_side):
        return False
    others = [o for o in (outcomes or []) if not _side_matches(o, lean_side)]
    return any(_side_matches(pick_side, o) for o in others)


def annotate_contrarian(result: dict, lean_by_market: dict) -> int:
    """Deterministic backstop for the contrarian tag — only a GENUINE divergence:
    the historically-sharp money sits OPPOSITE the raw-money crowd AND the pick
    follows the sharp side. It never fires when raw and sharp agree — e.g. a
    longshot future where the dollars pile onto 'No' purely by base rate; backing
    'Yes' there is a longshot, not a contrarian call. Never overrides a tag the
    model already set. Returns how many picks it tagged."""
    picks = result.get("picks", {}) or {}
    tagged = 0
    for bucket in BUCKETS:
        for p in picks.get(bucket, []) or []:
            if str(p.get("tag", "none") or "none").strip().lower() not in ("none", ""):
                continue  # respect the model's own tag (may be hedge/contrarian)
            info = lean_by_market.get(p.get("market", ""))
            if not info or not info.get("sharp_present"):
                continue
            raw, sharp = info.get("lean_side"), info.get("sharp_lean_side")
            if not raw or not sharp or _side_matches(raw, sharp):
                continue  # no data, or sharp agrees with the crowd -> not contrarian
            pick = p.get("pick", "")
            if _side_matches(pick, sharp) and _opposes_raw_lean(pick, raw, info.get("outcomes")):
                p["tag"] = "contrarian"
                if not p.get("tag_note"):
                    p["tag_note"] = f"sharp money on {sharp} vs raw crowd on {raw}"
                tagged += 1
    return tagged


_CONV_RANK = {"high": 0, "medium": 1, "low": 2}


def enforce_tag_budget(result: dict) -> int:
    """Hard backstop for tag discipline: at most ONE 'hedge' and ONE
    'contrarian' pick per slate, and a 'hedge' must actually oppose — a pick
    that wins TOGETHER with another pick (same side, e.g. the same team at an
    adjacent spread) is stacked exposure wearing a hedge label, and there's
    nothing to offset in a one-pick slate. Surplus/invalid tagged picks are
    DROPPED, not untagged: untagging a contrarian would ship a crowd-fade
    without its warning badge, and a surplus hedge was never a standalone
    bet. Within a tag, the highest-conviction pick survives. Runs AFTER
    annotate_contrarian so the backstop's own tags are budgeted too.
    Returns how many picks were dropped."""
    picks = result.get("picks", {}) or {}
    flat = [(b, p) for b in BUCKETS for p in (picks.get(b) or [])]

    def tag_of(p):
        return str(p.get("tag", "none") or "none").strip().lower()

    def conv_rank(p):
        return _CONV_RANK.get(str(p.get("conviction", "") or "").strip().lower(), 3)

    doomed = []
    hedges = [(b, p) for b, p in flat if tag_of(p) == "hedge"]
    all_picks = [p for _, p in flat]
    # A hedge that shares its side with any other pick offsets nothing.
    real_hedges = []
    for b, p in hedges:
        others = [o for o in all_picks if o is not p]
        if not others or any(_side_matches(p.get("pick"), o.get("pick")) for o in others):
            doomed.append(p)
        else:
            real_hedges.append((b, p))
    for group in (real_hedges,
                  [(b, p) for b, p in flat if tag_of(p) == "contrarian"]):
        if len(group) > 1:
            group.sort(key=lambda bp: conv_rank(bp[1]))
            doomed.extend(p for _, p in group[1:])

    if doomed:
        for b in BUCKETS:
            picks[b] = [p for p in (picks.get(b) or []) if not any(p is d for d in doomed)]
        result["picks"] = picks
    return len(doomed)


# Suggested stake, in UNITS (1 unit = 1% of bankroll). Sizing is fractional
# Kelly, seeded by the two things already on every pick: conviction and price.
# Conviction sets Moby's assumed EDGE over the market price (how much more likely
# it thinks the pick is than the ~price implies); Kelly turns that edge + the
# pick's odds into an optimal bankroll fraction; we bet a conservative FRACTION
# of Kelly (default 1/4) and cap it. This is deterministic (computed in code, not
# by the model) and inherently payoff-aware: it sizes down high-variance
# longshots and up confident value, and refuses a stake with no positive edge.
_UNIT_EDGE = {"high": 0.05, "medium": 0.03, "low": 0.015}
_UNIT_PCT = 1.0  # 1 unit = 1% of bankroll


def suggest_units(conviction, price):
    """Return a suggested stake in units (float, rounded to 0.5) or None.

    Kelly: f* = p - (1-p)/b, with p = price + conviction-edge (Moby's win-prob
    estimate) and b = (1/price) - 1 (net odds from the price). Bet KELLY_FRACTION
    of f*, express as units (1u = 1% bankroll), floor 0.5, cap MAX_UNITS.
    """
    p_mkt = _to_float(price, 0.0)
    if not (0.0 < p_mkt < 1.0):
        return None
    edge = _UNIT_EDGE.get(str(conviction or "").strip().lower())
    if not edge:
        return None
    kelly_fraction = float(os.environ.get("KELLY_FRACTION", "0.25"))
    max_units = float(os.environ.get("MAX_UNITS", "5"))
    p = min(p_mkt + edge, 0.97)          # estimated true win probability
    b = (1.0 / p_mkt) - 1.0              # net decimal odds implied by the price
    if b <= 0:
        return None
    kelly = p - (1.0 - p) / b            # full-Kelly bankroll fraction
    if kelly <= 0:
        return None                      # no positive edge -> suggest nothing
    units = (kelly * kelly_fraction) * 100.0 / _UNIT_PCT
    units = min(units, max_units)
    units = round(units * 2) / 2         # nearest 0.5
    return units if units >= 0.5 else 0.5


def annotate_units(result: dict) -> int:
    """Attach a suggested stake (p['units']) to each pick, from conviction+price.
    Returns how many picks got a stake."""
    picks = result.get("picks", {}) or {}
    n = 0
    for bucket in BUCKETS:
        for p in picks.get(bucket, []) or []:
            u = suggest_units(p.get("conviction"), p.get("price"))
            if u is not None:
                p["units"] = u
                n += 1
    return n

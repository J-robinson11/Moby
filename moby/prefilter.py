"""Stage A ($0, code only): curate the model's view of the market list.

attach_smart_money already ranked the list (last-chance first, strongest sharp
signal first) — this stage caps it to PREFILTER_TOP_N and compacts each market
to the fields the model actually reasons over: window flags, prices/payouts,
smart-money leans, top sharps. Raw holder tables, internals, and IDs stay out.
Junk out — room for high-value context (news brief, track record, X feed) in.
"""
from moby.config import knob

# The market fields the model sees, verbatim.
_MARKET_KEEP = (
    "event", "question", "market_type", "status", "last_chance", "starts",
    "outcomes", "implied_prob", "payout_by_outcome",
)
# The smart-money summary fields worth tokens (full holder tables are not).
_SM_KEEP = (
    "lean_side", "lean_pct", "total_smart_money_usd",
    "sharp_lean_side", "sharp_lean_pct", "sharp_traders_present",
)


def compact_market(m: dict) -> dict:
    """One market's model-facing view."""
    out = {k: m[k] for k in _MARKET_KEEP if k in m}
    for k in ("mins_to_kickoff", "mins_since_kickoff"):
        if k in m:
            out[k] = m[k]
    sm = m.get("smart_money") or {}
    compact_sm = {k: sm[k] for k in _SM_KEEP if k in sm}
    if sm.get("notable_sharps"):
        compact_sm["notable_sharps"] = sm["notable_sharps"][:3]
    if sm.get("top_holders"):
        compact_sm["top_holders"] = sm["top_holders"][:3]
    if compact_sm:
        out["smart_money"] = compact_sm
    return out


def prefilter_markets(markets: list, profile=None) -> list:
    """Cap the already-ranked list and compact each market."""
    top_n = int(knob("PREFILTER_TOP_N", "30", profile))
    return [compact_market(m) for m in markets[:top_n]]

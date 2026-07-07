"""Smart money: holder summaries weighted by lifetime-PnL 'sharpness'."""
from moby.polymarket import _to_float, fetch_holders, fetch_sharp_traders


def sharp_weight(pnl) -> float:
    """Map a trader's lifetime PnL to a sharpness multiplier."""
    if pnl is None:
        return 1.0          # not a known sharp — count at face value
    if pnl >= 1_000_000:
        return 4.0
    if pnl >= 250_000:
        return 3.0
    if pnl >= 50_000:
        return 2.0
    return 1.5              # on the leaderboard but smaller lifetime profit


def summarize_holders(market: dict, holders_raw: list, sharp: dict = None) -> dict:
    """Boil raw holder lists into a smart-money + sharp-money summary.

    - Dollar exposure ≈ shares * outcome price (money actually at risk).
    - 'Sharp' money additionally weights each holder by their lifetime PnL, so a
      historically profitable whale counts more than a merely-large position.
    """
    sharp = sharp or {}
    outcomes = market["outcomes"]
    prices = market["implied_prob"]

    def price_for(idx):
        return prices[idx] if isinstance(idx, int) and 0 <= idx < len(prices) else 0.0

    def name_for(idx):
        return outcomes[idx] if isinstance(idx, int) and 0 <= idx < len(outcomes) else f"outcome {idx}"

    value_by_outcome = {}        # raw USD exposure
    sharp_by_outcome = {}        # PnL-weighted USD exposure
    all_holders = []             # (usd, idx, name)
    notable_sharps = []          # known-sharp holders with lifetime PnL
    for group in holders_raw or []:
        for h in group.get("holders", []) or []:
            idx = h.get("outcomeIndex")
            amt = _to_float(h.get("amount"))
            usd = amt * price_for(idx)
            side = name_for(idx)
            wallet = (h.get("proxyWallet") or "").lower()
            info = sharp.get(wallet)
            pnl = info["pnl"] if info else None
            weight = sharp_weight(pnl) if info else 1.0
            display = (
                (info["name"] if info else None) or h.get("name") or h.get("pseudonym")
                or (wallet[:8] if wallet else "anon")
            )
            all_holders.append((usd, idx, display))
            value_by_outcome[side] = value_by_outcome.get(side, 0.0) + usd
            sharp_by_outcome[side] = sharp_by_outcome.get(side, 0.0) + usd * weight
            if info:
                notable_sharps.append({
                    "name": display, "side": side,
                    "position_usd": round(usd, 0), "lifetime_pnl": round(pnl, 0),
                })

    value_by_outcome = {k: round(v, 0) for k, v in value_by_outcome.items()}
    sharp_by_outcome = {k: round(v, 0) for k, v in sharp_by_outcome.items()}
    total = sum(value_by_outcome.values())
    sharp_total = sum(sharp_by_outcome.values())

    lean_side = max(value_by_outcome, key=value_by_outcome.get) if value_by_outcome else None
    lean_pct = round(100 * value_by_outcome.get(lean_side, 0) / total, 1) if total else 0.0
    sharp_lean = max(sharp_by_outcome, key=sharp_by_outcome.get) if sharp_by_outcome else None
    sharp_pct = round(100 * sharp_by_outcome.get(sharp_lean, 0) / sharp_total, 1) if sharp_total else 0.0

    top = sorted(all_holders, key=lambda t: t[0], reverse=True)[:5]
    top_holders = [{"name": n, "side": name_for(i), "usd": round(v, 0)} for v, i, n in top]
    notable_sharps.sort(key=lambda x: x["lifetime_pnl"], reverse=True)

    return {
        "smart_money_usd_by_outcome": value_by_outcome,
        "total_smart_money_usd": round(total, 0),
        "lean_side": lean_side,
        "lean_pct": lean_pct,                       # % of raw big money on lean_side
        "sharp_money_by_outcome": sharp_by_outcome,
        "sharp_lean_side": sharp_lean,              # where the HISTORICALLY SHARP money leans
        "sharp_lean_pct": sharp_pct,
        "sharp_traders_present": len(notable_sharps),
        "notable_sharps": notable_sharps[:5],       # name, side, position, lifetime PnL
        "top_holders": top_holders,
        "holders_counted": len(all_holders),
    }


def attach_smart_money(markets: list, min_smart_usd: float) -> list:
    """Fetch + attach holder summaries; drop markets with little big money.

    Keeps condition_id on each market (used later for logging + grading); it is
    stripped from the model's view in run_analysis.
    """
    sharp = fetch_sharp_traders()
    kept = []
    for m in markets:
        summary = summarize_holders(m, fetch_holders(m["condition_id"]), sharp)
        if summary["total_smart_money_usd"] < min_smart_usd:
            continue
        m["smart_money"] = summary
        kept.append(m)
    # Match-level markets FIRST (game props, then player props), futures last —
    # the user wants today's games prioritized, not the giant tournament futures.
    # Within each type, strongest sharp signal first.
    type_rank = {"game_prop": 0, "player_prop": 1, "other": 2, "future": 3}
    kept.sort(
        key=lambda x: (
            0 if x.get("last_chance") else 1,   # games before the next run lead the view
            type_rank.get(x.get("market_type"), 2),
            -x["smart_money"]["sharp_traders_present"],
            -x["smart_money"]["sharp_lean_pct"],
            -x["smart_money"]["total_smart_money_usd"],
        )
    )
    return kept

"""Holder summaries: dollar-weighted lean and sharp (PnL-weighted) lean."""
import moby


def test_summarize_holders_dollar_weighted_lean():
    market = {"outcomes": ["Yes", "No"], "implied_prob": [0.8, 0.2]}
    raw = [
        {"token": "yes", "holders": [
            {"outcomeIndex": 0, "amount": 1000, "name": "Whale"},
        ]},
        {"token": "no", "holders": [
            {"outcomeIndex": 1, "amount": 1000, "name": "Minnow"},
        ]},
    ]
    s = moby.summarize_holders(market, raw)
    # Yes: 1000 * 0.8 = 800; No: 1000 * 0.2 = 200 -> lean Yes ~80%
    assert s["lean_side"] == "Yes", s
    assert 75 <= s["lean_pct"] <= 85, s
    assert s["total_smart_money_usd"] == 1000, s


def test_sharp_money_flips_lean():
    # Sharp weighting: a high-PnL whale on the smaller side flips the SHARP
    # lean even when raw money leans the other way.
    mk = {"outcomes": ["Yes", "No"], "implied_prob": [0.8, 0.2]}
    raw2 = [
        {"holders": [{"outcomeIndex": 0, "amount": 1000, "proxyWallet": "0xAAA"}]},
        {"holders": [{"outcomeIndex": 1, "amount": 2000, "proxyWallet": "0xBBB", "name": "Sharp"}]},
    ]
    sharp = {"0xbbb": {"pnl": 2_000_000, "name": "Theo4", "rank": "1"}}
    s2 = moby.summarize_holders(mk, raw2, sharp)
    assert s2["lean_side"] == "Yes", s2          # raw money on Yes
    assert s2["sharp_lean_side"] == "No", s2     # sharp money flips to No
    assert s2["sharp_traders_present"] == 1, s2


def test_sharp_weight_tiers():
    assert moby.sharp_weight(2_000_000) == 4.0
    assert moby.sharp_weight(None) == 1.0

"""Stage A: cap the ranked list, compact each market's model view."""
from moby.prefilter import compact_market, prefilter_markets
from moby.sports.base import SportProfile
from moby.sports.soccer import SOCCER


def _mkt(i, last_chance=False):
    return {
        "event": "Alpha vs. Beta - More Markets",
        "question": f"Total goals over {i}.5",
        "market_type": "game_prop",
        "condition_id": f"c{i}",
        "starts": "2035-07-03 03:00:00+00",
        "status": "upcoming",
        "mins_to_kickoff": 120,
        "last_chance": last_chance,
        "outcomes": ["Yes", "No"],
        "implied_prob": [0.5, 0.5],
        "payout_by_outcome": {"Yes": {"price": 0.5, "profit_pct": 100, "multiple": 2.0}},
        "volume24hr": 123.0,
        "liquidity": 5000.0,
        "smart_money": {
            "smart_money_usd_by_outcome": {"Yes": 800.0, "No": 200.0},
            "total_smart_money_usd": 1000,
            "lean_side": "Yes", "lean_pct": 80.0,
            "sharp_money_by_outcome": {"Yes": 3200.0, "No": 200.0},
            "sharp_lean_side": "Yes", "sharp_lean_pct": 94.1,
            "sharp_traders_present": 4,
            "notable_sharps": [{"name": f"s{j}"} for j in range(5)],
            "top_holders": [{"name": f"h{j}"} for j in range(5)],
            "holders_counted": 40,
        },
    }


def test_prefilter_caps_and_preserves_rank_order(monkeypatch):
    ms = [_mkt(i) for i in range(50)]
    out = prefilter_markets(ms, SOCCER)
    assert len(out) == 30  # PREFILTER_TOP_N default
    assert [o["question"] for o in out] == [m["question"] for m in ms[:30]]
    monkeypatch.setenv("PREFILTER_TOP_N", "5")
    assert len(prefilter_markets(ms, SOCCER)) == 5


def test_compact_market_drops_junk_keeps_signal():
    c = compact_market(_mkt(1, last_chance=True))
    # Junk / internals out.
    assert "condition_id" not in c
    assert "volume24hr" not in c and "liquidity" not in c
    # Window flags, prices, payouts in.
    assert c["last_chance"] is True and c["status"] == "upcoming"
    assert c["mins_to_kickoff"] == 120
    assert c["payout_by_outcome"]["Yes"]["profit_pct"] == 100
    # Smart-money leans in; raw dollar tables and counters out; lists trimmed.
    sm = c["smart_money"]
    assert sm["lean_side"] == "Yes" and sm["sharp_lean_side"] == "Yes"
    assert sm["sharp_traders_present"] == 4
    assert len(sm["notable_sharps"]) == 3 and len(sm["top_holders"]) == 3
    assert "smart_money_usd_by_outcome" not in sm
    assert "sharp_money_by_outcome" not in sm
    assert "holders_counted" not in sm


def test_profile_defaults_can_set_top_n():
    p = SportProfile(
        key="t", label="T", market_tag="t", webhook_env="W",
        game_strong=("x",), player_hints=("y",), future_hints=("z",),
        novelty=(), live_grace_min=10, sport_prompt="s", search_hints="h",
        defaults={"PREFILTER_TOP_N": "3"},
    )
    assert len(prefilter_markets([_mkt(i) for i in range(10)], p)) == 3

"""Pick post-processing: pruning, JSON parsing, contrarian backstop, sizing."""
import moby


def test_prune_low_upside_drops_locks():
    # Zero/low-upside picks are pruned (a 100c lock must never ship).
    r = {"picks": {"game_props": [
        {"market": "lock", "pick": "Yes", "price": 1.0, "conviction": "High"},
        {"market": "value", "pick": "X", "price": 0.55, "conviction": "High"},
    ], "player_props": [], "futures": []}}
    assert moby.prune_low_upside(r, max_price=0.90) == 1
    assert [p["market"] for p in r["picks"]["game_props"]] == ["value"]


def test_parse_json_block_handles_fenced_output():
    # JSON parsing handles a fenced block like the model returns.
    sample = '''Here is my read.
    ```json
    {"picks": {"game_props": [], "player_props": [], "futures": []},
     "watchlist": ["USA props"], "summary": "Quiet."}
    ```'''
    parsed = moby.parse_json_block(sample)
    assert parsed["summary"] == "Quiet."
    assert moby.flatten_picks(parsed) == []


def test_annotate_contrarian_only_genuine_divergence():
    # Deterministic backstop tags ONLY a genuine divergence: sharp money
    # opposite the raw crowd AND the pick follows sharp. A longshot where
    # raw & sharp agree (both "No") is NOT contrarian even though backing
    # "Yes" opposes the raw dollars (this is the France-future false
    # positive we fixed). Model-set tags are never overridden.
    rr = {"picks": {"game_props": [
        {"market": "BTTS", "pick": "Yes", "conviction": "Medium"},                 # sharp Yes vs raw No -> contrarian
        {"market": "Longshot", "pick": "Yes", "conviction": "Low"},                # raw & sharp both No -> NOT contrarian
        {"market": "Total", "pick": "Yes", "conviction": "Low", "tag": "hedge"},    # model tag -> keep
    ], "player_props": [], "futures": []}}
    lean = {
        "BTTS":     {"lean_side": "No", "sharp_lean_side": "Yes", "sharp_present": 1, "outcomes": ["Yes", "No"]},
        "Longshot": {"lean_side": "No", "sharp_lean_side": "No",  "sharp_present": 2, "outcomes": ["Yes", "No"]},
        "Total":    {"lean_side": "No", "sharp_lean_side": "Yes", "sharp_present": 1, "outcomes": ["Yes", "No"]},
    }
    assert moby.annotate_contrarian(rr, lean) == 1
    gp = rr["picks"]["game_props"]
    assert gp[0]["tag"] == "contrarian", gp[0]
    assert gp[1].get("tag", "none") in ("none", None), gp[1]  # longshot, not contrarian
    assert gp[2]["tag"] == "hedge", gp[2]  # model's tag preserved


def test_suggest_units_fractional_kelly():
    # Suggested stake (units) via fractional Kelly from conviction+price:
    # higher conviction sizes up, no-edge picks get nothing, capped at MAX_UNITS.
    assert moby.suggest_units("High", 0.5) >= moby.suggest_units("Medium", 0.5) >= moby.suggest_units("Low", 0.5)
    assert moby.suggest_units("Low", 1.0) is None      # priced out -> no stake
    assert moby.suggest_units("bogus", 0.5) is None    # unknown conviction
    assert 0 < moby.suggest_units("High", 0.85) <= 5   # capped at MAX_UNITS


def test_annotate_units_attaches_stake():
    ur = {"picks": {"game_props": [
        {"market": "M", "pick": "Over", "conviction": "High", "price": 0.6},
    ], "player_props": [], "futures": []}, "summary": "s"}
    assert moby.annotate_units(ur) == 1 and ur["picks"]["game_props"][0]["units"] > 0
    # ...and it renders as a "Stake" card field.
    up = moby.build_discord_payload({**ur, "_run_slot": "5:00 PM"})
    assert any(f["name"] == "Stake" for e in up["embeds"] for f in e.get("fields", []))

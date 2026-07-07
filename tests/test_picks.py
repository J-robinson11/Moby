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


def test_tag_budget_drops_same_side_hedge():
    # The mislabeled-hedge case from the 2026-07-07 test run: a "hedge" on the
    # SAME side as another pick (one team at two adjacent spreads) wins
    # together with it — that's stacked exposure, so the backstop drops it.
    r = {"picks": {"game_props": [
        {"market": "Spread: NY (-5.5)", "pick": "Dallas Wings", "conviction": "High"},
        {"market": "Spread: NY (-4.5)", "pick": "Dallas Wings", "conviction": "Medium", "tag": "hedge"},
    ], "player_props": [], "futures": []}}
    assert moby.enforce_tag_budget(r) == 1
    assert [p["market"] for p in r["picks"]["game_props"]] == ["Spread: NY (-5.5)"]


def test_tag_budget_caps_one_contrarian_keeps_strongest():
    # Two contrarians -> only the higher-conviction one survives; a single
    # genuinely-opposing hedge is within budget and untouched.
    r = {"picks": {"game_props": [
        {"market": "A", "pick": "Under 2.5", "conviction": "Low", "tag": "contrarian"},
        {"market": "B", "pick": "Over 3.5", "conviction": "High", "tag": "contrarian"},
        {"market": "C", "pick": "Team X", "conviction": "Medium"},
        {"market": "D", "pick": "Under 1.5 first half", "conviction": "Medium", "tag": "hedge"},
    ], "player_props": [], "futures": []}}
    assert moby.enforce_tag_budget(r) == 1
    kept = r["picks"]["game_props"]
    tags = [p.get("tag") for p in kept]
    assert tags.count("contrarian") == 1 and tags.count("hedge") == 1
    assert next(p for p in kept if p.get("tag") == "contrarian")["conviction"] == "High"


def test_tag_budget_hedge_needs_something_to_offset():
    # A one-pick slate can't contain a hedge — there is nothing to offset.
    r = {"picks": {"game_props": [
        {"market": "A", "pick": "Under 2.5", "conviction": "High", "tag": "hedge"},
    ], "player_props": [], "futures": []}}
    assert moby.enforce_tag_budget(r) == 1
    assert r["picks"]["game_props"] == []


def test_tag_budget_leaves_disciplined_slates_alone():
    # One opposing hedge + one contrarian + untagged picks = within budget.
    r = {"picks": {"game_props": [
        {"market": "A", "pick": "Team X", "conviction": "High"},
        {"market": "B", "pick": "Under 2.5", "conviction": "Medium", "tag": "hedge"},
        {"market": "C", "pick": "Team Y", "conviction": "Medium", "tag": "contrarian"},
    ], "player_props": [], "futures": []}}
    assert moby.enforce_tag_budget(r) == 0
    assert len(r["picks"]["game_props"]) == 3

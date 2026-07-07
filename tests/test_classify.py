"""Market classification, timestamp parsing, and clean_markets selection."""
import time

import moby


def test_classify_market_buckets():
    assert moby.classify_market("Argentina vs Brazil total goals", "")[1] == "game_prop"
    assert moby.classify_market("Messi to score anytime", "")[1] == "player_prop"
    assert moby.classify_market("Brazil to win the World Cup", "")[1] == "future"


def test_parse_ts_space_plus00_gamestarttime_is_future():
    # A "+00"/space gameStartTime parses as a real FUTURE kickoff and is
    # preferred over a past creation date — otherwise upcoming props look
    # long-finished and get grace-dropped.
    future = moby._parse_ts("2035-07-03 03:00:00+00")
    assert future > time.time(), "space/+00 gameStartTime must parse as future"
    assert moby._parse_ts("2035-07-03 03:00:00+00", "2020-01-01T00:00:00Z") == future


def _mkt(q, cid):
    return {"question": q, "closed": False, "active": True, "liquidity": "5000",
            "spread": "0.02", "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
            "conditionId": cid, "gameStartTime": "2035-07-03 03:00:00+00"}


def test_clean_markets_selection_and_coverage():
    # Selection / coverage regressions (the bug where upcoming games surfaced
    # no props).
    alpha = {"title": "Alpha vs. Beta - More Markets",
             "markets": [_mkt(f"Total goals over {i}.5", f"a{i}") for i in range(100)]}
    gamma = {"title": "Gamma vs. Delta",
             "markets": [_mkt(f"Total goals over {i}.5", f"g{i}") for i in range(6)]}
    novelty = {"title": "What will the announcers say during Alpha vs Beta",
               "markets": [_mkt(f"phrase {i}", f"n{i}") for i in range(5)]}
    fut = {"title": "World Cup Winner",
           "markets": [_mkt(f"Will Team{i} win the World Cup?", f"f{i}") for i in range(10)]}
    sel = moby.clean_markets([alpha, gamma, novelty, fut], 500.0, 0.07)
    skeys = [moby._game_key(m["event"]) for m in sel]
    # Novelty markets skipped entirely.
    assert not any("announcers" in k.lower() for k in skeys), "novelty must be filtered"
    # A small game isn't starved by a 100-market game (per-game diversity).
    assert sum(1 for m in sel if moby._game_key(m["event"]) == "Gamma vs. Delta") == 6, skeys
    # Futures present but capped at FUTURES_SLOTS (default 4).
    assert 1 <= sum(1 for m in sel if m["market_type"] == "future") <= 4


def test_game_key_collapses_event_variants():
    # _game_key collapses a game's several events into one key.
    assert moby._game_key("Alpha vs. Beta - Player Props") == "Alpha vs. Beta"

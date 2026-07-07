"""NBA classification + registry tests.

Phrasings mirror real Polymarket (tag_slug=nba): per-game events like
"Lakers vs. Celtics" with game/player-prop markets, plus season futures
("NBA: 2027 Champion", NBA Cup, conference champions, win totals, awards). The
load-bearing case is the over/under collision (player stat lines must NOT be
swept up as game props) — same rule as WNBA. It's the offseason when this
ships, so the in-season phrasings below are validated against Polymarket's
conventions rather than live data.
"""
from moby.config import knob
from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles
from moby.sports.nba import NBA


def _label(question, event):
    return classify_market(question, event, NBA)[1]


# --- Game props -------------------------------------------------------------
def test_total_points_is_game_prop():
    # "Total Points Over 224.5" contains "points" (a player hint) but game_strong
    # "total points" is scanned first → game_prop.
    assert _label("Lakers vs. Celtics: Total Points Over 224.5",
                  "Lakers vs. Celtics") == "game_prop"


def test_ou_via_vs_event_is_game_prop():
    assert _label("Lakers vs. Celtics: O/U 224.5", "Lakers vs. Celtics") == "game_prop"


def test_spread_is_game_prop():
    assert _label("Spread: Lakers (-4.5)", "Lakers vs. Celtics") == "game_prop"


def test_bare_vs_moneyline_is_game_prop():
    assert _label("Will the Lakers win the game?", "Lakers vs. Celtics") == "game_prop"


# --- Player props -----------------------------------------------------------
def test_points_over_is_player_prop():
    # The collision case: player props read "... O/U N.5" but must NOT match a
    # game_strong phrase; the stat word "points" lands them as player props.
    assert _label("LeBron James: Points O/U 27.5",
                  "Lakers vs. Celtics - Player Props") == "player_prop"


def test_triple_double_is_player_prop():
    assert _label("Nikola Jokic to record a triple-double",
                  "Nuggets vs. Suns - Player Props") == "player_prop"


def test_threes_over_is_player_prop():
    assert _label("Stephen Curry: Threes Over 4.5",
                  "Warriors vs. Kings - Player Props") == "player_prop"


# --- Futures ----------------------------------------------------------------
def test_finals_champion_future():
    assert _label("Will the Celtics win the 2027 NBA Finals?",
                  "NBA: 2027 Champion") == "future"


def test_nba_cup_future():
    assert _label("Will the Lakers win the 2026 NBA Cup?", "NBA Cup") == "future"


def test_conference_champion_future():
    assert _label("Will the Boston Celtics win the East?",
                  "NBA: 2027 Eastern Conference Champion") == "future"


def test_rookie_of_the_year_future():
    assert _label("Will AJ Dybantsa win the 2026-27 NBA Rookie of the Year?",
                  "NBA: 2026-27 Rookie of the Year") == "future"


def test_win_total_is_future():
    # Same trace as NFL: bare "over" is NOT in GAME_STRONG, so "win total" fires.
    assert _label("Lakers regular season win total over 48.5",
                  "NBA Win Totals") == "future"


# --- Offseason speculation correctly falls to "other" -----------------------
def test_next_team_speculation_is_other():
    # Free-agency speculation names no bettable market type → "other". NOT
    # blacklisted; the pipeline's season gate keeps the sport dark.
    assert _label("Will LeBron James play for the Atlanta Hawks in 2026-27?",
                  "NBA: LeBron James Next Team") == "other"


def test_retire_speculation_is_other():
    assert _label("Will LeBron James retire before next NBA season?",
                  "Will LeBron James retire before next NBA season?") == "other"


# --- Registry ---------------------------------------------------------------
def test_nba_registered():
    assert "nba" in SPORTS


def test_get_profiles_full_order():
    assert [p.key for p in get_profiles("soccer,wnba,ufc,nfl,nba")] == [
        "soccer", "wnba", "ufc", "nfl", "nba"
    ]


# --- Knob precedence (NBA sets liquidity defaults, mirroring WNBA) -----------
def test_knob_falls_back_to_nba_default(monkeypatch):
    monkeypatch.delenv("MIN_LIQUIDITY", raising=False)
    assert knob("MIN_LIQUIDITY", "500", NBA) == "250"


def test_knob_env_beats_nba_default(monkeypatch):
    monkeypatch.setenv("MIN_LIQUIDITY", "999")
    assert knob("MIN_LIQUIDITY", "500", NBA) == "999"

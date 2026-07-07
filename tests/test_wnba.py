"""WNBA reference-adapter classification, registry, and knob-precedence tests.

Phrasings mirror real Polymarket (tag_slug=wnba): futures events like
"WNBA: 2026 Champion", per-game events like "Aces vs. Liberty" with game/
player-prop markets. The load-bearing case is the over/under collision: WNBA
player props ALWAYS read "... Over N.5", so they must NOT be swept up as game
props by the totals phrases.
"""
from moby.config import knob
from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles
from moby.sports.wnba import WNBA


def _label(question, event):
    return classify_market(question, event, WNBA)[1]


# --- Game props -------------------------------------------------------------
def test_total_points_is_game_prop():
    # "Total Points Over 165.5" contains "points" (a player hint) but game_strong
    # is scanned first and "total points" wins → game_prop.
    assert _label("Aces vs. Liberty: Total Points Over 165.5",
                  "Aces vs. Liberty") == "game_prop"


def test_bare_vs_moneyline_is_game_prop():
    # No game_strong / player hit → the bare "X vs Y" fallback → game_prop.
    assert _label("Will the Aces beat the Liberty?",
                  "Aces vs. Liberty") == "game_prop"


def test_spread_is_game_prop():
    assert _label("Aces -6.5 spread", "Aces vs. Liberty") == "game_prop"


# --- Player props -----------------------------------------------------------
def test_player_points_over_is_player_prop():
    # The collision case: player props read "... Over N.5" but must NOT match a
    # game_strong phrase; the stat word "points" lands them as player props.
    assert _label("A'ja Wilson: Points Over 21.5",
                  "Aces vs. Liberty - Player Props") == "player_prop"


def test_double_double_is_player_prop():
    assert _label("Breanna Stewart to record a double-double",
                  "Liberty vs. Sun - Player Props") == "player_prop"


def test_assists_over_is_player_prop():
    assert _label("Caitlin Clark: Assists Over 8.5",
                  "Fever vs. Sky - Player Props") == "player_prop"


# --- Futures ----------------------------------------------------------------
def test_champion_future():
    assert _label("WNBA: 2026 Champion", "WNBA: 2026 Champion") == "future"


def test_finals_winner_future():
    assert _label("Will the Aces win the 2026 WNBA Finals?",
                  "WNBA: 2026 Champion") == "future"


def test_mvp_future():
    assert _label("WNBA: 2026 MVP", "WNBA: 2026 MVP") == "future"


# --- Registry ---------------------------------------------------------------
def test_wnba_registered():
    assert "wnba" in SPORTS


def test_get_profiles_multi_returns_both_in_order():
    assert [p.key for p in get_profiles("soccer,wnba")] == ["soccer", "wnba"]


# --- Knob precedence --------------------------------------------------------
def test_knob_falls_back_to_profile_default(monkeypatch):
    monkeypatch.delenv("MIN_LIQUIDITY", raising=False)
    assert knob("MIN_LIQUIDITY", "500", WNBA) == "250"


def test_knob_env_beats_profile_default(monkeypatch):
    monkeypatch.setenv("MIN_LIQUIDITY", "999")
    assert knob("MIN_LIQUIDITY", "500", WNBA) == "999"


# --- Live-phrasing regression (caught by classifying real API data) ----------
def test_postseason_market_is_future():
    # Real phrasing has "2026 WNBA" mid-phrase, so the compound hint
    # "make the playoffs" never fires — bare "playoffs" must catch it.
    assert _label("Will the Atlanta Dream make the 2026 WNBA Playoffs?",
                  "WNBA: Team To Make Postseason") == "future"


def test_ou_abbreviation_both_directions():
    # Polymarket abbreviates to "O/U": game totals go via the vs-event check,
    # player stat lines via PLAYER_HINTS — neither depends on "over"/"under".
    assert _label("Chicago Sky vs. Phoenix Mercury: O/U 173.5",
                  "Chicago Sky vs. Phoenix Mercury") == "game_prop"
    assert _label("Kahleah Copper: Points O/U 19.5",
                  "Chicago Sky vs. Phoenix Mercury") == "player_prop"

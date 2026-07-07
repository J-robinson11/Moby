"""NFL classification + registry tests.

Phrasings mirror real Polymarket (tag_slug=nfl): per-game events like
"Chiefs vs. Ravens" with game/player-prop markets, plus season futures
("NFL Champion 2027", division champions, win totals, MVP). The load-bearing
cases are the over/under collision (player stat lines must NOT be swept up as
game props) and the win-total-is-future trace. It's the offseason when this
ships, so the in-season phrasings below are validated against Polymarket's
conventions rather than live data.
"""
from moby.config import knob
from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles
from moby.sports.nfl import NFL


def _label(question, event):
    return classify_market(question, event, NFL)[1]


# --- Game props -------------------------------------------------------------
def test_total_points_is_game_prop():
    # "Total Points Over 47.5" contains "points" but no player hint fires;
    # game_strong "total points" wins → game_prop.
    assert _label("Chiefs vs. Ravens: Total Points Over 47.5",
                  "Chiefs vs. Ravens") == "game_prop"


def test_ou_via_vs_event_is_game_prop():
    # "O/U 47.5" carries no game_strong phrase, but the vs-event fallback fires.
    assert _label("Chiefs vs. Ravens: O/U 47.5", "Chiefs vs. Ravens") == "game_prop"


def test_spread_is_game_prop():
    assert _label("Spread: Chiefs (-3.5)", "Chiefs vs. Ravens") == "game_prop"


def test_bare_vs_moneyline_is_game_prop():
    assert _label("Will the Chiefs win the game?", "Chiefs vs. Ravens") == "game_prop"


# --- Player props -----------------------------------------------------------
def test_passing_yards_over_is_player_prop():
    # The collision case: the stat line reads "... O/U N.5" but must NOT match a
    # game_strong phrase; "passing yards" lands it as a player prop.
    assert _label("Patrick Mahomes: Passing Yards O/U 275.5",
                  "Chiefs vs. Ravens - Player Props") == "player_prop"


def test_rushing_yards_over_is_player_prop():
    assert _label("Saquon Barkley: Rushing Yards Over 89.5",
                  "Eagles vs. Cowboys - Player Props") == "player_prop"


def test_anytime_td_is_player_prop():
    assert _label("Travis Kelce: Anytime TD",
                  "Chiefs vs. Ravens - Player Props") == "player_prop"


def test_receptions_over_is_player_prop():
    assert _label("Tyreek Hill: Receptions Over 5.5",
                  "Dolphins vs. Bills - Player Props") == "player_prop"


# --- Futures ----------------------------------------------------------------
def test_super_bowl_future():
    assert _label("Will the Chiefs win the 2027 Super Bowl?",
                  "NFL Champion 2027") == "future"


def test_division_champion_future():
    # Live phrasing: "Will Houston Texans win the 2026 AFC South?"
    assert _label("Will the Cowboys win the 2026 NFC East?",
                  "Pro Football: NFC East Champion") == "future"


def test_mvp_future():
    assert _label("Will Josh Allen win the 2026 NFL MVP?",
                  "Pro Football: 2026 MVP Winner") == "future"


def test_playoffs_future():
    # Live phrasing: "Will the Arizona Cardinals make the 2027 NFL Playoffs?"
    assert _label("Will the Ravens make the 2027 NFL Playoffs?",
                  "Pro Football: Team to Make Postseason") == "future"


def test_win_total_is_future():
    # The load-bearing trace: bare "over" is NOT in GAME_STRONG, so no game hit,
    # no player hit, no "X vs Y", then "win total" in FUTURE_HINTS fires → future
    # (must NOT be misread as a game total).
    assert _label("Chiefs regular season win total over 9.5",
                  "Pro Football: Win Totals") == "future"


# --- Novelty (halftime show collides with the "halftime" game hint) ---------
def test_halftime_show_is_novelty():
    # The Super Bowl halftime-show performer market must be blacklisted so it
    # isn't misfiled as a game_prop via the "halftime" hint.
    q = "Will Taylor Swift perform at the 2027 Big Game halftime show?"
    ev = "Who will perform at the 2027 Big Game halftime show?"
    assert any(n in (ev + " " + q).lower() for n in NFL.novelty)


# --- Offseason speculation correctly falls to "other" -----------------------
def test_next_team_speculation_is_other():
    # Roster speculation names no bettable market type → "other"; the pipeline's
    # season gate keeps the sport dark. NOT blacklisted.
    assert _label("Will Tyreek Hill play for the Kansas City Chiefs next?",
                  "Where will Tyreek Hill play in 2026?") == "other"


def test_retire_speculation_is_other():
    assert _label("Will Aaron Rodgers retire before next season?",
                  "Will Aaron Rodgers retire before next season?") == "other"


# --- Registry ---------------------------------------------------------------
def test_nfl_registered():
    assert "nfl" in SPORTS


def test_get_profiles_includes_nfl():
    assert [p.key for p in get_profiles("soccer,wnba,nfl")] == ["soccer", "wnba", "nfl"]

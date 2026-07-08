"""MLB adapter classification, novelty, caps, and registry tests.

Phrasings mirror real Polymarket (tag_slug=mlb, live-validated 2026-07-08:
198 events / 4,094 markets). Load-bearing cases: (a) the stat-line collision —
player props read "Colby Thomas: Home Runs O/U 0.5", so bare "o/u" must not
appear in game_strong; (b) game totals ("Brewers vs. Cardinals: O/U 7.5")
carry NO keyword and must fall through player hints to the " vs " check;
(c) the volume caps — MLB's whole reason for profile defaults.
"""
from moby.config import knob
from moby.markets import classify_market, clean_markets
from moby.sports import SPORTS, get_profiles
from moby.sports.mlb import MLB


def _label(question, event):
    return classify_market(question, event, MLB)[1]


# --- Game props -------------------------------------------------------------
def test_moneyline_is_game_prop():
    assert _label("Milwaukee Brewers vs. St. Louis Cardinals",
                  "Milwaukee Brewers vs. St. Louis Cardinals") == "game_prop"


def test_run_line_spread_is_game_prop():
    assert _label("Spread: Milwaukee Brewers (-1.5)",
                  "Milwaukee Brewers vs. St. Louis Cardinals") == "game_prop"


def test_game_total_falls_through_to_vs_check():
    # "X vs. Y: O/U 7.5" has NO game_strong keyword and must NOT hit a player
    # stat hint — the bare " vs " fallback owns it.
    assert _label("Milwaukee Brewers vs. St. Louis Cardinals: O/U 7.5",
                  "Milwaukee Brewers vs. St. Louis Cardinals") == "game_prop"


def test_first_five_innings_is_game_prop():
    assert _label("Seattle Mariners vs. Miami Marlins: 1st 5 Innings O/U 3.5",
                  "Seattle Mariners vs. Miami Marlins") == "game_prop"


def test_extra_innings_is_game_prop():
    assert _label("Will the game go to extra innings?: Seattle Mariners vs. Miami Marlins",
                  "Seattle Mariners vs. Miami Marlins") == "game_prop"


# --- Player props (the stat-line collision) ----------------------------------
def test_home_run_prop_is_player_prop():
    # Live phrasing. Event title contains " vs. ", so the player hint MUST win
    # before the vs-fallback fires.
    assert _label("Colby Thomas: Home Runs O/U 0.5",
                  "Athletics vs. Detroit Tigers") == "player_prop"


def test_pitcher_strikeouts_is_player_prop():
    assert _label("Tarik Skubal: Strikeouts O/U 6.5",
                  "Athletics vs. Detroit Tigers") == "player_prop"


def test_total_bases_is_player_prop():
    assert _label("Fernando Tatis Jr.: Total Bases O/U 1.5",
                  "Diamondbacks vs. Padres") == "player_prop"


# --- Futures -----------------------------------------------------------------
def test_world_series_is_future():
    assert _label("Will the New York Yankees win the 2026 World Series?",
                  "MLB: 2026 World Series Champion") == "future"


def test_award_ladder_is_future():
    # Live phrasing from the award farms (600+ such markets on the tag).
    assert _label("Will Gabriel Moreno win the 2026 NL Platinum Glove award?",
                  "2026 NL Platinum Glove") == "future"


def test_season_wins_is_future():
    assert _label("New York Yankees: Regular Season Wins O/U 92.5",
                  "MLB: 2026 Regular Season Win Totals") == "future"


# --- Novelty blacklist (front-office gossip) ----------------------------------
def test_draft_and_manager_markets_are_novelty_dropped():
    events = [{
        "title": "2026 MLB Draft: Player to be Drafted in the Top 10",
        "markets": [{"question": "Will Grady Emerson be drafted in the top 10 in the 2026 MLB Draft?",
                     "active": True, "liquidity": 5000, "spread": 0.01,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]'}],
    }, {
        # "be the next" not "next manager": live phrasing splices the team in
        # ("be the next RED SOX manager"), the WNBA compound-hint lesson.
        "title": "MLB: Next Red Sox Manager",
        "markets": [{"question": "Will Rocco Baldelli be the next Red Sox manager?",
                     "active": True, "liquidity": 5000, "spread": 0.01,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]'}],
    }]
    assert clean_markets(events, 500, 0.07, MLB) == []


# --- Volume caps (the reason this profile exists) ------------------------------
def test_mlb_per_game_caps_are_tightened():
    # ~15 games/day with O/U + spread ladders: global caps (30/15) would let
    # 3 games eat the 100-market candidate cap. MLB slices per game instead.
    assert knob("MAX_GAME_PROPS_PER_GAME", "30", MLB) == "8"
    assert knob("MAX_PLAYER_PROPS_PER_GAME", "15", MLB) == "6"


def test_env_still_overrides_mlb_caps(monkeypatch):
    monkeypatch.setenv("MAX_GAME_PROPS_PER_GAME", "12")
    assert knob("MAX_GAME_PROPS_PER_GAME", "30", MLB) == "12"


# --- Registry -----------------------------------------------------------------
def test_mlb_registered_and_selectable():
    assert "mlb" in SPORTS
    assert get_profiles("mlb") == [MLB]
    assert MLB.webhook_env == "DISCORD_WEBHOOK_URL_MLB"
    assert MLB.market_tag == "mlb"

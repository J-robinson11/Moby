"""UFC classification + registry tests.

Phrasings mirror real Polymarket (tag_slug=ufc): fight events titled
"UFC 329: Max Holloway vs. Conor McGregor (Welterweight, Main Card)" whose
winner market hits the bare "X vs. Y" fallback, per-fight method/round markets
("Will the fight be won by KO or TKO?", "O/U 2.5 Rounds"), belt/ranking futures
("Who will be UFC Lightweight champion at the end of 2026?") and next-opponent
futures ("Will Ilia Topuria fight Paddy Pimblett next?"). The pure
will-he-compete question stays in "other".
"""
from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles
from moby.sports.ufc import UFC


def _label(question, event):
    return classify_market(question, event, UFC)[1]


# --- Game props (fight-level markets) ---------------------------------------
def test_bare_vs_fight_is_game_prop():
    # The fight's winner market: no game_strong/player hit, but the event title
    # carries "vs." → the bare "X vs Y" fallback → game_prop.
    assert _label("UFC 329: Max Holloway vs. Conor McGregor (Welterweight, Main Card)",
                  "UFC 329: Max Holloway vs. Conor McGregor (Welterweight, Main Card)") == "game_prop"


def test_ko_tko_method_is_game_prop():
    assert _label("Will the fight be won by KO or TKO?",
                  "UFC 320: Ankalaev vs. Pereira (Light Heavyweight, Main Card)") == "game_prop"


def test_submission_method_is_game_prop():
    assert _label("Will the fight be won by submission?",
                  "UFC 320: Ankalaev vs. Pereira (Light Heavyweight, Main Card)") == "game_prop"


def test_go_the_distance_is_game_prop():
    assert _label("Fight to Go the Distance?",
                  "UFC 320: Ankalaev vs. Pereira (Light Heavyweight, Main Card)") == "game_prop"


def test_round_total_ou_is_game_prop():
    # Round totals read "O/U N.5 Rounds" — caught by "rounds", NOT by a bare
    # over/under hint (there is none in GAME_STRONG).
    assert _label("O/U 2.5 Rounds",
                  "UFC 320: Ankalaev vs. Pereira (Light Heavyweight, Main Card)") == "game_prop"


def test_per_fighter_ko_is_game_prop():
    # A per-fighter method line is still a fight-level market.
    assert _label("Will Alex Pereira win by KO or TKO?",
                  "UFC 320: Ankalaev vs. Pereira (Light Heavyweight, Main Card)") == "game_prop"


# --- Player props (fighter-stat lines) --------------------------------------
def test_significant_strikes_is_player_prop():
    assert _label("Magomed Ankalaev: Significant Strikes Over 45.5",
                  "UFC 320: Ankalaev vs. Pereira - Fighter Props") == "player_prop"


def test_takedowns_is_player_prop():
    assert _label("Alex Pereira takedowns over 1.5",
                  "UFC 320: Ankalaev vs. Pereira - Fighter Props") == "player_prop"


# --- Futures ----------------------------------------------------------------
def test_belt_champion_future():
    assert _label("Will Ilia Topuria be the UFC Lightweight Champion on December 31, 2026?",
                  "Who will be UFC Lightweight champion at the end of 2026?") == "future"


def test_pound_for_pound_future():
    assert _label("Will Islam Makhachev remain #1 in the UFC Pound-For-Pound Rankings?",
                  "Who will be the next UFC Pound-For-Pound #1 in 2026?") == "future"


def test_next_opponent_future():
    # Next-opponent speculation is routed to "future" (both title variants:
    # "... fight next?" and "... Next Fight").
    assert _label("Will Ilia Topuria fight Paddy Pimblett next?",
                  "UFC: Ilia Topuria Next Fight") == "future"
    assert _label("Will Merab Dvalishvili fight Petr Yan next?",
                  "Who will Merab Dvalishvili fight next?") == "future"


# --- Other (genuine non-bet) ------------------------------------------------
def test_will_he_compete_is_other():
    # Pure will-he-even-fight speculation names no priceable outcome → "other".
    assert _label("Will Conor McGregor Fight in 2026?",
                  "UFC: Will Conor McGregor Fight in 2026?") == "other"


# --- Registry ---------------------------------------------------------------
def test_ufc_registered():
    assert "ufc" in SPORTS


def test_get_profiles_includes_ufc():
    assert [p.key for p in get_profiles("soccer,wnba,ufc")] == ["soccer", "wnba", "ufc"]


# --- Knob precedence (UFC sets liquidity defaults) --------------------------
def test_knob_falls_back_to_ufc_default(monkeypatch):
    monkeypatch.delenv("MIN_LIQUIDITY", raising=False)
    from moby.config import knob
    assert knob("MIN_LIQUIDITY", "500", UFC) == "250"


def test_knob_env_beats_ufc_default(monkeypatch):
    monkeypatch.setenv("MIN_LIQUIDITY", "999")
    from moby.config import knob
    assert knob("MIN_LIQUIDITY", "500", UFC) == "999"


# --- game_key: fight titles carry no " - ", so the default is a no-op --------
def test_ufc_uses_default_game_key():
    # No override registered; the default _game_key leaves fight titles intact.
    assert UFC.game_key is None

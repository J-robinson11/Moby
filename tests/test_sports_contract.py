"""Adapter contract: a new sport can't half-register."""
import pytest

from moby.config import knob
from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles

# Per-sport game window (issue #7): each sport wakes on its own rhythm — daily
# sports at the global 18h, gappy schedules wider so they don't go dark between
# games / cards. This is the source of truth the pipeline reads via knob().
_EXPECTED_WINDOW = {
    "soccer": "48",   # WC knockout rest days (~44h gaps)
    "wnba": "18",     # near-daily
    "ufc": "96",      # fight week — weekly cards
    "nfl": "48",      # Thu/Sun/Mon clusters; preview Sunday from Sat
    "nba": "18",      # near-daily
    "mlb": "18",      # ~15 games every day
}

_SAMPLES = (
    ("Team A vs Team B total points", "Team A vs. Team B"),
    ("Somebody to score anytime", "Team A vs. Team B - Player Props"),
    ("Will Team A win the championship?", "Champion"),
)


def test_every_profile_is_complete():
    for key, p in SPORTS.items():
        assert p.key == key
        assert p.label, key
        assert p.market_tag, key
        assert p.webhook_env, key
        assert p.game_strong and p.player_hints and p.future_hints, key
        assert p.live_grace_min > 0, key
        assert p.sport_prompt and p.search_hints, key


def test_every_profile_classifies_into_valid_buckets():
    for p in SPORTS.values():
        for question, event in _SAMPLES:
            priority, label = classify_market(question, event, p)
            assert label in ("game_prop", "player_prop", "future", "other"), (p.key, question)
            assert priority in (0, 1, 2, 3), (p.key, question)


def test_every_profile_declares_its_window(monkeypatch):
    # Every sport sets WINDOW_HOURS explicitly so its timing is visible and
    # editable per-file (issue #7) — the pipeline reads exactly this via knob().
    monkeypatch.delenv("WINDOW_HOURS", raising=False)
    for key, p in SPORTS.items():
        assert key in _EXPECTED_WINDOW, f"new sport {key} must declare its window"
        assert knob("WINDOW_HOURS", "18", p) == _EXPECTED_WINDOW[key], key


def test_env_window_overrides_every_profile(monkeypatch):
    # The ops escape hatch: env beats every per-sport default.
    monkeypatch.setenv("WINDOW_HOURS", "6")
    for p in SPORTS.values():
        assert knob("WINDOW_HOURS", "18", p) == "6", p.key


def test_get_profiles_defaults_to_soccer(monkeypatch):
    monkeypatch.delenv("MOBY_SPORTS", raising=False)
    assert [p.key for p in get_profiles()] == ["soccer"]


def test_get_profiles_env_selection(monkeypatch):
    monkeypatch.setenv("MOBY_SPORTS", " Soccer ")
    assert [p.key for p in get_profiles()] == ["soccer"]


def test_get_profiles_unknown_sport_is_startup_error():
    with pytest.raises(ValueError, match="quidditch"):
        get_profiles("soccer,quidditch")


def test_get_profiles_empty_is_startup_error():
    with pytest.raises(ValueError):
        get_profiles(" , ")

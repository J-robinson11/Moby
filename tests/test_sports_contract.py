"""Adapter contract: a new sport can't half-register."""
import pytest

from moby.markets import classify_market
from moby.sports import SPORTS, get_profiles

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

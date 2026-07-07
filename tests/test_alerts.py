"""Webhook routing — each sport posts to its own Discord channel, with a
legacy fallback when its secret is unset. No network: requests.post is stubbed
to capture the URL it would have hit."""
from types import SimpleNamespace

import moby.alerts as alerts
from moby.sports.soccer import SOCCER

# A fake sport with a NON-legacy webhook env so we can prove per-sport routing.
_WNBA = SimpleNamespace(key="wnba", label="WNBA", webhook_env="DISCORD_WEBHOOK_URL_WNBA")

_RESULT = {"picks": {"game_props": [], "player_props": [], "futures": []},
           "summary": "Quiet.", "watchlist": ["x"], "_run_slot": "7:00 AM"}


def _capture_post(monkeypatch):
    """Redirect requests.post to record the URL and return a 200-ish stub."""
    seen = {}

    def _post(url, **kw):
        seen["url"] = url
        return SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr(alerts.requests, "post", _post)
    return seen


def test_profile_webhook_used_when_set(monkeypatch):
    seen = _capture_post(monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL_WNBA", "https://wnba-hook")
    alerts.send_alert(_RESULT, _WNBA)
    assert seen["url"] == "https://wnba-hook"


def test_empty_sport_webhook_falls_back_to_legacy(monkeypatch):
    # GitHub Actions sets an EMPTY STRING for a missing secret — must count as
    # unset and fall back to the legacy channel.
    seen = _capture_post(monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL_WNBA", "")
    alerts.send_alert(_RESULT, _WNBA)
    assert seen["url"] == "https://legacy"


def test_profile_none_uses_legacy(monkeypatch):
    seen = _capture_post(monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy")
    alerts.send_alert(_RESULT, None)
    assert seen["url"] == "https://legacy"


def test_soccer_profile_uses_legacy_env(monkeypatch):
    # Soccer's webhook_env IS the legacy var, so it routes there directly.
    seen = _capture_post(monkeypatch)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy")
    alerts.send_alert(_RESULT, SOCCER)
    assert seen["url"] == "https://legacy"

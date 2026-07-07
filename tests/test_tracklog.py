"""log_signals stamps each row with its sport. The log path is redirected to a
tmp file so nothing touches the real signals_log.jsonl."""
import json

import moby.tracklog as tracklog


def _result():
    return {"picks": {
        "game_props": [{"market": "A vs B total", "pick": "Over", "conviction": "High"}],
        "player_props": [],
        "futures": [],
    }, "summary": "one play"}


def _rows(log_file):
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


def test_log_signals_stamps_sport(tmp_path, monkeypatch):
    log_file = tmp_path / "signals_log.jsonl"
    monkeypatch.setattr(tracklog, "_log_path", lambda: str(log_file))
    tracklog.log_signals(_result(), "2026-07-07T00:00:00Z", {}, sport="wnba")
    rows = _rows(log_file)
    assert len(rows) == 1
    assert rows[0]["sport"] == "wnba"


def test_log_signals_defaults_sport_to_soccer(tmp_path, monkeypatch):
    log_file = tmp_path / "signals_log.jsonl"
    monkeypatch.setattr(tracklog, "_log_path", lambda: str(log_file))
    tracklog.log_signals(_result(), "2026-07-07T00:00:00Z", {})  # sport omitted
    rows = _rows(log_file)
    assert rows[0]["sport"] == "soccer"

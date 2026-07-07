"""load_track_record scopes grading to one sport. The log path and the market
resolver are monkeypatched, so there's no filesystem-of-record touch and no
network — grading always sees a deterministic (closed, "Yes") resolution."""
import json

import moby.factors as factors


def _write_log(tmp_path, rows):
    log_file = tmp_path / "signals_log.jsonl"
    log_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return log_file


def _row(sport, market, pick="Yes", cid="c1"):
    r = {"market": market, "smart_money_side": pick, "condition_id": cid,
         "market_type": "game_prop"}
    if sport is not None:  # a field-less row = legacy soccer
        r["sport"] = sport
    return r


def test_track_record_scopes_to_sport(tmp_path, monkeypatch):
    log_file = _write_log(tmp_path, [
        _row(None, "Legacy soccer no-sport-field"),   # field-less = soccer
        _row("soccer", "Soccer game"),
        _row("wnba", "WNBA game 1"),
        _row("wnba", "WNBA game 2"),
    ])
    # factors.py imports _log_path from tracklog at module level, so patch the
    # name bound INSIDE factors. Resolution is stubbed to avoid the network.
    monkeypatch.setattr(factors, "_log_path", lambda: str(log_file))
    monkeypatch.setattr(factors, "fetch_market_resolution", lambda cid: (True, "Yes"))

    soccer = factors.load_track_record(sport="soccer")
    wnba = factors.load_track_record(sport="wnba")

    # soccer counts the field-less legacy row PLUS the explicit soccer row (2).
    assert soccer["total_logged"] == 2
    assert soccer["graded"] == 2 and soccer["wins"] == 2
    # wnba counts only the two wnba rows.
    assert wnba["total_logged"] == 2
    assert wnba["graded"] == 2 and wnba["wins"] == 2


def test_track_record_unscoped_counts_all(tmp_path, monkeypatch):
    log_file = _write_log(tmp_path, [
        _row(None, "Legacy soccer"),
        _row("wnba", "WNBA game"),
    ])
    monkeypatch.setattr(factors, "_log_path", lambda: str(log_file))
    monkeypatch.setattr(factors, "fetch_market_resolution", lambda cid: (True, "Yes"))
    all_rows = factors.load_track_record()  # no sport → every row
    assert all_rows["total_logged"] == 2

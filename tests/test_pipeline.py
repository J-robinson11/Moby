"""main() fault isolation: one sport's exception must not sink its siblings,
and main() reports a non-zero exit iff ANY sport failed. Everything the loop
touches — prepare_sport, run_synthesis, finish_sport, get_profiles, Anthropic —
is stubbed, so there's no network and NO ANTHROPIC_API_KEY requirement."""
from types import SimpleNamespace

import moby.pipeline as pipeline

_A = SimpleNamespace(key="alpha", label="Alpha")
_B = SimpleNamespace(key="beta", label="Beta")


def _patch_common(monkeypatch, profiles):
    """Stub the API client + profile registry; return a list capturing finishes."""
    monkeypatch.setattr(pipeline, "Anthropic", lambda **kw: SimpleNamespace(name="stub"))
    monkeypatch.setattr(pipeline, "get_profiles", lambda: profiles)
    # run_synthesis just echoes a stub result per job key.
    monkeypatch.setattr(pipeline, "run_synthesis",
                        lambda client, jobs: {k: {"summary": f"{k} ok"} for k in jobs})
    finished = []
    monkeypatch.setattr(pipeline, "finish_sport",
                        lambda prep, result: finished.append(prep["profile"].key))
    return finished


def test_one_sport_failing_does_not_sink_the_other(monkeypatch):
    finished = _patch_common(monkeypatch, [_A, _B])

    def _prepare(client, profile):
        if profile.key == "alpha":
            raise RuntimeError("alpha exploded")
        return {"profile": profile, "user": "u"}

    monkeypatch.setattr(pipeline, "prepare_sport", _prepare)
    rc = pipeline.main()
    assert rc == 1                 # one sport failed
    assert finished == ["beta"]    # the other still completed


def test_all_success_returns_zero(monkeypatch):
    finished = _patch_common(monkeypatch, [_A, _B])
    monkeypatch.setattr(pipeline, "prepare_sport",
                        lambda client, profile: {"profile": profile, "user": "u"})
    rc = pipeline.main()
    assert rc == 0
    assert sorted(finished) == ["alpha", "beta"]


def test_quiet_exit_is_not_a_failure(monkeypatch):
    # prepare returning None (no candidates) is a quiet skip, not a failure.
    finished = _patch_common(monkeypatch, [_A, _B])
    monkeypatch.setattr(pipeline, "prepare_sport",
                        lambda client, profile: None if profile.key == "alpha"
                        else {"profile": profile, "user": "u"})
    rc = pipeline.main()
    assert rc == 0
    assert finished == ["beta"]


def test_finish_failure_is_isolated(monkeypatch):
    # An exception during finish for one sport marks failure but the loop goes on.
    _patch_common(monkeypatch, [_A, _B])
    monkeypatch.setattr(pipeline, "prepare_sport",
                        lambda client, profile: {"profile": profile, "user": "u"})
    done = []

    def _finish(prep, result):
        if prep["profile"].key == "alpha":
            raise RuntimeError("alpha finish blew up")
        done.append(prep["profile"].key)

    monkeypatch.setattr(pipeline, "finish_sport", _finish)
    rc = pipeline.main()
    assert rc == 1
    assert done == ["beta"]


# --- season gate --------------------------------------------------------------
def test_has_game_window_cases():
    live = {"market_type": "game_prop", "status": "live"}
    soon = {"market_type": "player_prop", "status": "upcoming", "mins_to_kickoff": 300}
    far = {"market_type": "game_prop", "status": "upcoming", "mins_to_kickoff": 10_000}
    future = {"market_type": "future", "status": "future"}
    other = {"market_type": "other", "status": "upcoming", "mins_to_kickoff": 60}
    assert pipeline.has_game_window([live], 18)
    assert pipeline.has_game_window([future, soon], 18)
    assert not pipeline.has_game_window([far, future, other], 18)  # 18h = 1080 min
    assert not pipeline.has_game_window([], 18)


def test_prepare_sport_gates_offseason_before_holder_fetches(monkeypatch):
    # A futures-only sport (NFL in July) must quiet-exit BEFORE the ~100
    # /holders calls — the whole point of enabling every sport year-round.
    profile = SimpleNamespace(key="nfl", label="NFL", market_tag="nfl", defaults={})
    monkeypatch.setattr(pipeline, "fetch_events", lambda tag: [{"stub": True}])
    monkeypatch.setattr(
        pipeline, "clean_markets",
        lambda ev, lq, sp, prof: [
            {"market_type": "future", "status": "future"},
            {"market_type": "other", "status": "upcoming", "mins_to_kickoff": 99999},
        ])

    def _boom(*a, **kw):
        raise AssertionError("attach_smart_money must not run for a gated sport")

    monkeypatch.setattr(pipeline, "attach_smart_money", _boom)
    assert pipeline.prepare_sport(SimpleNamespace(name="client"), profile) is None


# --- TEST_RUN tagging ----------------------------------------------------------
def _finish_fixture():
    prep = {"profile": SimpleNamespace(key="t", label="T"), "markets": [],
            "cid_by_market": {}, "track_record": {}, "slot": "5:00 PM", "now": "now"}
    result = {"picks": {"game_props": [], "player_props": [], "futures": []}, "summary": "s"}
    return prep, result


def test_finish_sport_test_run_skips_logging(monkeypatch):
    monkeypatch.setenv("TEST_RUN", "1")
    logged, alerted = [], []
    monkeypatch.setattr(pipeline, "log_signals", lambda *a, **kw: logged.append(a))
    monkeypatch.setattr(pipeline, "send_alert", lambda result, profile=None: alerted.append(result))
    prep, result = _finish_fixture()
    pipeline.finish_sport(prep, result)
    assert result["_test_run"] is True
    assert logged == []          # a test slate never enters the track record
    assert len(alerted) == 1     # but the alert still ships — that's the point


def test_finish_sport_normal_run_logs(monkeypatch):
    logged = []
    monkeypatch.setattr(pipeline, "log_signals",
                        lambda *a, **kw: logged.append(kw.get("sport")))
    monkeypatch.setattr(pipeline, "send_alert", lambda result, profile=None: None)
    prep, result = _finish_fixture()
    pipeline.finish_sport(prep, result)
    assert "_test_run" not in result
    assert logged == ["t"]


def test_finish_sport_reports_combined_stage_cost(monkeypatch, capsys):
    # The per-sport Cost line must combine Stage B (news, from prep) with
    # Stage C (synthesis, from the result's _cost) — the JSON's _cost alone
    # undersells the run (it only covers synthesis).
    monkeypatch.setattr(pipeline, "send_alert", lambda result, profile=None: None)
    monkeypatch.setattr(pipeline, "log_signals", lambda *a, **kw: None)
    prep, result = _finish_fixture()
    prep["news_cost"] = 0.0892
    result["_cost"] = {"total_cost": 0.0295}
    pipeline.finish_sport(prep, result)
    assert result["_cost_run_total"] == 0.1187
    out = capsys.readouterr().out
    assert "Cost: $0.1187 this sport (news $0.0892 + synthesis $0.0295)" in out

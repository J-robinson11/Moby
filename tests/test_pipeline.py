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

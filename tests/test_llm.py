"""Model tiers, batch-with-fallback synthesis, and the Stage B news brief —
all against stub clients; no network, no API key."""
import json
from types import SimpleNamespace

from moby.llm import (
    build_synthesis_user,
    estimate_cost,
    resolve_models,
    run_news_brief,
    run_synthesis,
    wants_news_brief,
)
from moby.prompts import SYNTHESIS_BASE, synthesis_system
from moby.sports.soccer import SOCCER

_SLATE = '{"picks": {"game_props": [], "player_props": [], "futures": []}, "summary": "%s"}'


def _fake_msg(text):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200, server_tool_use=None),
    )


# --- model tiers -------------------------------------------------------------

def test_model_tier_defaults_and_precedence(monkeypatch):
    assert resolve_models() == ("claude-sonnet-4-6", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("ANTHROPIC_MODEL", "legacy-model")   # old secret still honored
    assert resolve_models()[0] == "legacy-model"
    monkeypatch.setenv("MODEL_SYNTH", "explicit-synth")     # explicit knob wins
    assert resolve_models()[0] == "explicit-synth"
    monkeypatch.setenv("MODEL_NEWS", "explicit-news")
    assert resolve_models()[1] == "explicit-news"


def test_estimate_cost_batch_half_price():
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=0, server_tool_use=None)
    full = estimate_cost("claude-sonnet-4-6", usage)
    half = estimate_cost("claude-sonnet-4-6", usage, batch=True)
    assert full["token_cost"] == 3.0 and half["token_cost"] == 1.5


# --- system blocks -----------------------------------------------------------

def test_synthesis_system_caches_shared_base_only():
    blocks = synthesis_system(SOCCER)
    assert blocks[0]["text"] == SYNTHESIS_BASE
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]
    assert "World Cup" in blocks[1]["text"]


# --- stage B -----------------------------------------------------------------

def test_wants_news_brief_gates_on_last_chance():
    assert wants_news_brief([{"last_chance": False}, {"last_chance": True}])
    assert not wants_news_brief([{"last_chance": False}, {"status": "future"}])
    assert not wants_news_brief([])


def test_run_news_brief_call_shape(monkeypatch):
    captured = {}

    def _create(**kw):
        captured.update(kw)
        return _fake_msg("Nothing notable in the last 48h.")

    client = SimpleNamespace(messages=SimpleNamespace(create=_create))
    markets = [
        {"event": "Alpha vs. Beta", "status": "upcoming",
         "starts": "2026-06-29T18:00:00Z", "last_chance": True},
        {"event": "Alpha vs. Beta", "status": "upcoming",   # duplicate event: listed once
         "starts": "2026-06-29T18:00:00Z", "last_chance": True},
        {"event": "Later Game", "status": "upcoming", "last_chance": False},
    ]
    out = run_news_brief(client, "claude-haiku-4-5-20251001", SOCCER, markets,
                         {"now_utc": "2026-06-29T21:20:00+00:00"})
    assert out["status"] == "ok" and "Nothing notable" in out["text"]
    assert captured["model"] == "claude-haiku-4-5-20251001"
    assert captured["tools"][0]["max_uses"] == 5  # NEWS_MAX_SEARCHES default
    user = captured["messages"][0]["content"]
    assert user.count("Alpha vs. Beta") == 1 and "Later Game" not in user
    monkeypatch.setenv("NEWS_MAX_SEARCHES", "2")
    run_news_brief(client, "m", SOCCER, markets, {})
    assert captured["tools"][0]["max_uses"] == 2


# --- stage C: batch + fallback ----------------------------------------------

def test_synthesis_user_carries_factors_but_not_costs():
    news = {"status": "ok", "text": "Brief text.", "_cost": {"total_cost": 1}}
    user = build_synthesis_user(SOCCER, [{"question": "Q"}], news,
                                {"note": "tr"}, {"status": "stub"}, {"now_utc": "T"})
    payload = json.loads(user.split("\n\n", 1)[1])
    assert payload["news_brief"] == {"status": "ok", "text": "Brief text."}
    assert payload["run_context"]["now_utc"] == "T"
    assert payload["markets"] == [{"question": "Q"}]


def test_run_synthesis_batch_success_no_direct_call():
    entry = SimpleNamespace(
        custom_id="soccer",
        result=SimpleNamespace(type="succeeded",
                               message=_fake_msg(f"```json\n{_SLATE % 'from batch'}\n```")),
    )
    submitted = {}

    def _create_batch(requests):
        submitted["requests"] = requests
        return SimpleNamespace(id="batch_1")

    def _no_direct(**kw):
        raise AssertionError("direct call must not happen when the batch succeeds")

    client = SimpleNamespace(messages=SimpleNamespace(
        create=_no_direct,
        batches=SimpleNamespace(
            create=_create_batch,
            retrieve=lambda bid: SimpleNamespace(processing_status="ended"),
            results=lambda bid: iter([entry]),
            cancel=lambda bid: None,
        ),
    ))
    out = run_synthesis(client, {"soccer": {"profile": SOCCER, "user": "u"}})
    assert out["soccer"]["summary"] == "from batch"
    assert out["soccer"]["_cost"]["token_cost"] == round((3.0 + 3.0) / 2 / 1000, 4)
    req = submitted["requests"][0]
    assert req["custom_id"] == "soccer"
    assert req["params"]["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_run_synthesis_timeout_cancels_and_falls_back(monkeypatch):
    monkeypatch.setenv("BATCH_WAIT_MIN", "0")   # expire immediately, no sleep
    cancelled = []
    client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: _fake_msg(f"```json\n{_SLATE % 'direct fallback'}\n```"),
        batches=SimpleNamespace(
            create=lambda requests: SimpleNamespace(id="batch_2"),
            retrieve=lambda bid: SimpleNamespace(processing_status="in_progress"),
            results=lambda bid: iter([]),
            cancel=lambda bid: cancelled.append(bid),
        ),
    ))
    out = run_synthesis(client, {"soccer": {"profile": SOCCER, "user": "u"}})
    assert cancelled == ["batch_2"]
    assert out["soccer"]["summary"] == "direct fallback"


def test_run_synthesis_errored_entry_falls_back():
    entry = SimpleNamespace(custom_id="soccer",
                            result=SimpleNamespace(type="errored"))
    client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: _fake_msg(f"```json\n{_SLATE % 'direct retry'}\n```"),
        batches=SimpleNamespace(
            create=lambda requests: SimpleNamespace(id="batch_3"),
            retrieve=lambda bid: SimpleNamespace(processing_status="ended"),
            results=lambda bid: iter([entry]),
            cancel=lambda bid: None,
        ),
    ))
    out = run_synthesis(client, {"soccer": {"profile": SOCCER, "user": "u"}})
    assert out["soccer"]["summary"] == "direct retry"


def test_batch_mode_off_goes_straight_to_direct(monkeypatch):
    monkeypatch.setenv("BATCH_MODE", "0")

    def _no_batch(*a, **kw):
        raise AssertionError("batch must not be used with BATCH_MODE=0")

    client = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: _fake_msg(f"```json\n{_SLATE % 'direct only'}\n```"),
        batches=SimpleNamespace(create=_no_batch),
    ))
    out = run_synthesis(client, {"soccer": {"profile": SOCCER, "user": "u"}})
    assert out["soccer"]["summary"] == "direct only"

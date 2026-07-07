"""Claude (Moby) — model tiers, the two-stage flow, cost estimation, parsing.

Stage B (run_news_brief): Haiku + web search, the only place search happens.
Stage C (run_synthesis): Sonnet-class, no tools, over the curated Stage-A view.
Every active sport rides ONE Messages Batch (50% off all tokens) with a
per-sport direct-call fallback, so an alert always ships.

The legacy single-call run_analysis is kept for compatibility with the old
surface; the pipeline no longer uses it.
"""
import json
import os
import time

from anthropic import Anthropic

from moby.config import knob
from moby.prompts import (
    ANALYSIS_INSTRUCTIONS,
    news_brief_instructions,
    synthesis_system,
)

MODEL_PRICING = {
    "haiku":  {"in": 1.00, "out": 5.00},
    "sonnet": {"in": 3.00, "out": 15.00},
    "opus":   {"in": 5.00, "out": 25.00},
}
WEB_SEARCH_COST = 0.01


def resolve_models() -> tuple:
    """(synthesis_model, news_model). MODEL_SYNTH / MODEL_NEWS envs win; the
    legacy ANTHROPIC_MODEL secret is still honored for synthesis."""
    synth = (os.environ.get("MODEL_SYNTH")
             or os.environ.get("ANTHROPIC_MODEL")
             or "claude-sonnet-4-6")
    news = os.environ.get("MODEL_NEWS") or "claude-haiku-4-5-20251001"
    return synth, news


def estimate_cost(model: str, usage, batch: bool = False) -> dict:
    price = next((v for k, v in MODEL_PRICING.items() if k in model), None)
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    searches = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    token_cost = 0.0
    if price:
        token_cost = (in_tok / 1_000_000) * price["in"] + (out_tok / 1_000_000) * price["out"]
        if batch:
            token_cost /= 2  # Batch API: 50% off all tokens
    search_cost = searches * WEB_SEARCH_COST
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "web_searches": searches,
        "token_cost": round(token_cost, 4),
        "search_cost": round(search_cost, 4),
        "total_cost": round(token_cost + search_cost, 4),
    }


def _text_of(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# ---------------------------------------------------------------------------
# Stage B — news brief (Haiku + web search, gated on last-chance games)
# ---------------------------------------------------------------------------
def wants_news_brief(markets: list) -> bool:
    """Stage B only pays for search when this window actually owns games."""
    return any(m.get("last_chance") for m in markets)


def run_news_brief(client, model: str, profile, markets: list, run_context: dict) -> dict:
    """Fetch a short factual scouting brief for this window's games."""
    max_uses = int(knob("NEWS_MAX_SEARCHES", "5", profile))
    games, seen = [], set()
    for m in markets:
        if not m.get("last_chance"):
            continue
        key = m.get("event", "")
        if key in seen:
            continue
        seen.add(key)
        games.append(f"- {key} ({m.get('status', '?')}, starts {m.get('starts', '?')})")
    user = (
        f"run_context: {json.dumps(run_context)}\n"
        "Games in this run's window (last chance to bet them):\n"
        + "\n".join(games)
    )
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=news_brief_instructions(profile),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
        messages=[{"role": "user", "content": user}],
    )
    cost = estimate_cost(model, resp.usage)
    print(f"[{profile.key}] Stage B news brief: ${cost['total_cost']:.4f} "
          f"({cost['web_searches']} searches, {cost['input_tokens']} in / "
          f"{cost['output_tokens']} out)")
    return {"status": "ok", "text": _text_of(resp).strip(), "_cost": cost}


# ---------------------------------------------------------------------------
# Stage C — synthesis (no tools; one batch for all sports, direct fallback)
# ---------------------------------------------------------------------------
def build_synthesis_user(profile, markets: list, news_brief: dict,
                         track_record: dict, x_sentiment: dict,
                         run_context: dict) -> str:
    """The Stage C user message: run timestamps + every factor block. This is
    the ONLY place run-varying content lives — the system blocks stay static
    so the batch's shared prefix can cache."""
    payload = {
        "run_context": run_context,
        "markets": markets,
        "news_brief": {k: v for k, v in (news_brief or {}).items()
                       if not k.startswith("_")},
        "track_record": track_record,
        "x_sentiment": x_sentiment,
    }
    return (
        f"Here are curated Polymarket {profile.label} markets with their "
        "smart-money summaries, a fresh news brief, your track record, and the "
        "X-sentiment slot. Weigh all factors and return today's slate as JSON.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )


def run_synthesis_direct(client, model: str, profile, user: str) -> dict:
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=synthesis_system(profile),
        messages=[{"role": "user", "content": user}],
    )
    cost = estimate_cost(model, resp.usage)
    print(f"[{profile.key}] Stage C synthesis (direct): ${cost['total_cost']:.4f} "
          f"[{cost['input_tokens']} in / {cost['output_tokens']} out]")
    result = parse_json_block(_text_of(resp))
    result["_cost"] = cost
    return result


def _batch_entry_result(entry, model: str):
    """Parse one batch result entry; None means 'retry this sport directly'."""
    if entry.result.type != "succeeded":
        print(f"  [{entry.custom_id}] batch entry {entry.result.type} — will retry direct")
        return None
    msg = entry.result.message
    cost = estimate_cost(model, msg.usage, batch=True)
    print(f"  [{entry.custom_id}] Stage C synthesis (batch): ${cost['total_cost']:.4f} "
          f"[{cost['input_tokens']} in / {cost['output_tokens']} out]")
    try:
        result = parse_json_block(_text_of(msg))
    except ValueError as exc:
        print(f"  [{entry.custom_id}] batch output unparseable — will retry direct: {exc}")
        return None
    result["_cost"] = cost
    return result


def run_synthesis_batch(client, model: str, jobs: dict,
                        wait_min: float = None, poll_sec: float = 30) -> dict:
    """Submit every sport's synthesis as ONE Messages Batch (50% off).

    jobs: {sport_key: {"profile": SportProfile, "user": str}}. Returns
    {sport_key: parsed-result-or-None}; an empty dict (timeout) or a None value
    (errored/unparseable entry) tells the caller to fall back to a direct call
    for that sport. On timeout the batch is cancelled so the job stays inside
    its time budget and an alert still ships.
    """
    if wait_min is None:
        wait_min = float(os.environ.get("BATCH_WAIT_MIN", "20"))
    requests = [
        {
            "custom_id": key,
            "params": {
                "model": model,
                "max_tokens": 8000,
                "system": synthesis_system(job["profile"]),
                "messages": [{"role": "user", "content": job["user"]}],
            },
        }
        for key, job in jobs.items()
    ]
    batch = client.messages.batches.create(requests=requests)
    print(f"Stage C batch {batch.id}: {len(requests)} sport(s) submitted, "
          f"waiting up to {wait_min:.0f} min")
    deadline = time.time() + wait_min * 60
    while time.time() < deadline:
        status = client.messages.batches.retrieve(batch.id)
        if status.processing_status == "ended":
            return {entry.custom_id: _batch_entry_result(entry, model)
                    for entry in client.messages.batches.results(batch.id)}
        time.sleep(min(poll_sec, max(1.0, deadline - time.time())))
    print(f"Stage C batch {batch.id} not finished after {wait_min:.0f} min — "
          "cancelling and falling back to direct calls.")
    try:
        client.messages.batches.cancel(batch.id)
    except Exception as exc:  # noqa: BLE001 — the fallback matters more than cleanup
        print(f"  batch cancel failed (continuing): {exc}")
    return {}


def run_synthesis(client, jobs: dict) -> dict:
    """Stage C for all active sports. Batch by default (BATCH_MODE != '0');
    any sport the batch didn't deliver falls back to a direct call."""
    model, _ = resolve_models()
    results = {}
    if os.environ.get("BATCH_MODE", "1") != "0":
        results = run_synthesis_batch(client, model, jobs)
    out = {}
    for key, job in jobs.items():
        result = results.get(key)
        if result is None:
            result = run_synthesis_direct(client, model, job["profile"], job["user"])
        out[key] = result
    return out


# ---------------------------------------------------------------------------
# Legacy single-call flow (pre-Phase-3). Kept for the public surface; the
# pipeline now runs the staged flow above.
# ---------------------------------------------------------------------------
def run_analysis(client: Anthropic, model: str, markets: list,
                 track_record: dict, x_sentiment: dict, run_context: dict) -> dict:
    # Strip internal-only fields from the model's view of each market.
    model_view = [
        {k: v for k, v in m.items() if not k.startswith("_") and k != "condition_id"}
        for m in markets
    ]
    payload = {
        "run_context": run_context,
        "markets": model_view,
        "track_record": track_record,
        "x_sentiment": x_sentiment,
    }
    user = (
        "Here are live Polymarket World Cup markets with their largest-holder "
        "(smart money) summaries, plus your track record and the X-sentiment slot. "
        "Weigh all factors and return today's slate as JSON.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=ANALYSIS_INSTRUCTIONS,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": user}],
    )

    cost = estimate_cost(model, resp.usage)
    print(
        f"Cost: ${cost['total_cost']:.4f} "
        f"(tokens ${cost['token_cost']:.4f} [{cost['input_tokens']} in / {cost['output_tokens']} out], "
        f"{cost['web_searches']} web searches ${cost['search_cost']:.4f})"
    )

    result = parse_json_block(_text_of(resp))
    result["_cost"] = cost
    return result


def parse_json_block(text: str) -> dict:
    """Extract the last JSON object from the model's reply (fenced or bare)."""
    candidates = []
    if "```" in text:
        for chunk in text.split("```"):
            c = chunk.strip()
            if c.startswith("json"):
                c = c[4:].strip()
            if c.startswith("{"):
                candidates.append(c)
    if not candidates:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start: end + 1])
    for c in reversed(candidates):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"Could not parse JSON from model output:\n{text[:800]}")

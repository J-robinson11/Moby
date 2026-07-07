"""Claude (Moby) — model calls, cost estimation, output parsing."""
import json

from anthropic import Anthropic

from moby.prompts import ANALYSIS_INSTRUCTIONS

MODEL_PRICING = {
    "haiku":  {"in": 1.00, "out": 5.00},
    "sonnet": {"in": 3.00, "out": 15.00},
    "opus":   {"in": 5.00, "out": 25.00},
}
WEB_SEARCH_COST = 0.01


def estimate_cost(model: str, usage) -> dict:
    price = next((v for k, v in MODEL_PRICING.items() if k in model), None)
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    searches = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    token_cost = 0.0
    if price:
        token_cost = (in_tok / 1_000_000) * price["in"] + (out_tok / 1_000_000) * price["out"]
    search_cost = searches * WEB_SEARCH_COST
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "web_searches": searches,
        "token_cost": round(token_cost, 4),
        "search_cost": round(search_cost, 4),
        "total_cost": round(token_cost + search_cost, 4),
    }


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

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    result = parse_json_block(text)
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

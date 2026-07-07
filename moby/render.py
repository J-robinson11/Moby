"""Discord embed rendering."""
from moby.picks import BUCKETS, flatten_picks
from moby.polymarket import _to_float
from moby.windows import run_slot_label

CONF_COLOR = {"High": 0x2ECC71, "Medium": 0xF1C40F, "Low": 0xE67E22}


def _clean(text, limit=220) -> str:
    """Strip citation tags / whitespace and truncate for a phone-sized field."""
    s = str(text or "").replace("\n", " ")
    # Drop any <cite ...>...</cite> wrappers the model might emit.
    while "<cite" in s and ">" in s:
        a = s.find("<cite")
        b = s.find(">", a)
        if b == -1:
            break
        s = s[:a] + s[b + 1:]
    s = s.replace("</cite>", "").strip()
    if len(s) > limit:
        s = s[:limit - 1].rstrip() + "…"
    return s or "n/a"


def _fmt_list(items) -> str:
    if not items:
        return "None noted this run."
    if isinstance(items, str):
        items = [items]
    return "\n".join(f"• {_clean(x, 160)}" for x in items[:3])[:1024]


_BUCKET_LABEL = {"game_props": "GAME PROP", "player_props": "PLAYER PROP", "futures": "FUTURE"}
# Contrarian/hedge flags: a small badge in the card title + a "Role" line.
# Conviction still drives the card color; these only ADD a marker.
TAG_BADGE = {"contrarian": "🔀 CONTRARIAN", "hedge": "⚖️ HEDGE"}
TAG_ROLE = {"contrarian": "Contrarian", "hedge": "Hedge"}


def build_discord_payload(result: dict) -> dict:
    summary = result.get("summary", "No bets this run.")
    watchlist = result.get("watchlist", [])
    tr = result.get("_track_record", {})
    n_eval = result.get("markets_evaluated")
    scanned = f" · {n_eval} markets" if n_eval else ""
    tr_note = f" · {tr.get('note')}" if tr.get("note") else ""
    slot = result.get("_run_slot") or run_slot_label()
    # Multi-sport: prefix the header with the sport label when the pipeline
    # tags the result (e.g. "World Cup"). Absent → the original single-sport
    # titles, byte-for-byte, so existing soccer output never drifts.
    label = result.get("_sport_label")
    head = f"🐋 Moby · {label}" if label else "🐋 Moby"
    # Manual TEST runs (workflow_dispatch test=1) post for real but are marked
    # unmistakably so a validation slate is never mistaken for a live signal.
    if result.get("_test_run"):
        head = f"🧪 TEST · {head}"

    picks = flatten_picks(result)
    if not picks:
        return {
            "username": "Moby",
            "embeds": [{
                "title": f"{head} — {slot} run · no bets",
                "description": _clean(summary, 400),
                "color": 0x95A5A6,
                "fields": [{"name": "Watchlist", "value": _fmt_list(watchlist), "inline": False}],
                "footer": {"text": f"Moby · multi-factor sentiment{scanned}{tr_note}"},
            }],
        }

    # Header embed summarizing the slate, then one card per pick (game→player→future).
    counts = {b: 0 for b in BUCKETS}
    for p in picks:
        counts[p["bucket"]] += 1
    header_lines = ", ".join(
        f"{counts[b]} {_BUCKET_LABEL[b].lower()}{'s' if counts[b] != 1 else ''}" for b in BUCKETS
    )
    embeds = [{
        "username": "Moby",
        "title": f"{head} — {slot} run",
        "description": f"{_clean(summary, 280)}\n\n**{header_lines}**",
        "color": 0x3498DB,
        "footer": {"text": f"Stakes in units (1u≈1% bankroll, ¼-Kelly) · futures = glance{scanned}{tr_note}"},
    }]
    for p in picks:
        conf = p.get("conviction", "Low")
        color = CONF_COLOR.get(conf, 0x95A5A6)
        price = p.get("price")
        price_str = f"{round(_to_float(price) * 100)}¢" if price not in (None, "") else "—"
        payout_str = _clean(p.get("payout"), 40)
        tag = str(p.get("tag", "") or "").strip().lower()
        # Compact: inline stats (incl. suggested stake), optional Role, why, risk.
        units = p.get("units")
        fields = [
            {"name": "Conviction", "value": conf, "inline": True},
            {"name": "Price", "value": price_str, "inline": True},
            {"name": "Payout", "value": payout_str, "inline": True},
        ]
        if units:
            u_str = f"{units:g}u"  # e.g. "2.5u" / "3u"
            fields.append({"name": "Stake", "value": u_str, "inline": True})
        if tag in TAG_ROLE:
            note = _clean(p.get("tag_note"), 120)
            role_val = TAG_ROLE[tag]
            if note and note.lower() not in ("none", "n/a"):
                role_val = f"{TAG_ROLE[tag]} — {note}"
            fields.append({"name": "Role", "value": role_val[:1024], "inline": False})
        fields.append({"name": "Why", "value": _clean(p.get("rationale") or p.get("smart_money"), 280), "inline": False})
        risk = _clean(p.get("contrarian_note"), 140)
        if risk and risk.lower() not in ("none", "n/a"):
            fields.append({"name": "Risk", "value": risk, "inline": False})
        title = f"[{_BUCKET_LABEL[p['bucket']]}] {p.get('pick')} · {price_str}"
        badge = TAG_BADGE.get(tag, "")
        if badge:
            title = f"{title} · {badge}"
        embeds.append({
            "title": title[:256],
            "description": _clean(p.get("market"), 200),
            "color": color,
            "fields": fields,
            "footer": {"text": "Sentiment read, not advice."},
        })

    return {"username": "Moby", "embeds": embeds[:10]}  # Discord max 10 embeds

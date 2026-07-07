"""Extra sentiment factors: track record (graded log) + X feeds (stub).

This module is the future-input home — the X/Twitter feed and any richer
track-record analytics land here as named factor blocks.
"""
import json
import os

from moby.polymarket import fetch_market_resolution
from moby.tracklog import _log_path


def load_track_record(grade_limit: int = 25, sport: str = None) -> dict:
    """Read signals_log.jsonl and grade resolved past picks (best-effort).

    Returns a compact summary used as a sentiment factor: how Moby's prior
    calls have actually resolved, by category, plus a few recent wins.

    Multi-sport: pass ``sport`` to scope both grading AND total_logged to that
    sport's rows only, so one sport's track record never leaks into another's
    prompt. Rows predating the sport field are soccer (matching the log's
    write-side default).
    """
    log_path = _log_path()
    if not os.path.exists(log_path):
        return {"status": "no_history", "note": "No prior signals logged yet."}

    rows = []
    try:
        with open(log_path) as f:
            for line in f.read().splitlines()[-300:]:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except Exception:  # noqa: BLE001
        return {"status": "unreadable", "note": "Could not read signal log."}

    if sport is not None:
        rows = [r for r in rows if r.get("sport", "soccer") == sport]

    graded = {"win": 0, "loss": 0}
    by_cat = {}
    recent_wins = []
    # Grade most-recent first, capped to bound network calls.
    for row in reversed(rows[-grade_limit:]):
        cid = row.get("condition_id")
        pick = row.get("smart_money_side") or row.get("pick")
        cat = row.get("market_type", "other")
        if not cid or not pick:
            continue
        closed, winner = fetch_market_resolution(cid)
        if not closed or winner is None:
            continue
        won = (str(pick).strip().lower() == str(winner).strip().lower())
        graded["win" if won else "loss"] += 1
        c = by_cat.setdefault(cat, {"win": 0, "loss": 0})
        c["win" if won else "loss"] += 1
        if won and len(recent_wins) < 5:
            recent_wins.append(f"{pick} — {row.get('market', '')[:60]}")

    total_graded = graded["win"] + graded["loss"]
    win_rate = round(100 * graded["win"] / total_graded, 1) if total_graded else None
    return {
        "status": "graded" if total_graded else "pending",
        "total_logged": len(rows),
        "graded": total_graded,
        "wins": graded["win"],
        "losses": graded["loss"],
        "win_rate_pct": win_rate,
        "by_category": by_cat,
        "recent_wins": recent_wins,
        "note": (
            f"{graded['win']}/{total_graded} graded picks won "
            f"({win_rate}%)." if total_graded else
            "Picks logged but none resolved yet — track record still building."
        ),
    }


def fetch_x_sentiment(markets: list) -> dict:
    """X/Twitter sentiment input. STUB — wired as a factor slot for later.

    Activates only if X_BEARER_TOKEN is set; even then returns a clearly-labeled
    placeholder until the feed integration is implemented.
    """
    if not os.environ.get("X_BEARER_TOKEN"):
        return {"status": "not_configured",
                "note": "X/Twitter feed not connected yet (planned input)."}
    return {"status": "stub",
            "note": "X_BEARER_TOKEN set but feed parsing not implemented yet."}

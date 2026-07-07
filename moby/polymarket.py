"""Polymarket API access: Gamma (markets/events) + Data (holders, leaderboard).

Also home to the small parsing helpers (_as_list, _to_float, _parse_ts) for the
mixed formats these endpoints return.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"
USER_AGENT = "moby-sentiment/1.0"


def fetch_events(tag_slug: str, limit: int = None) -> list:
    """Fetch open events for a tag, highest 24h volume first, from Gamma.

    Paginates (the API caps at ~100 events/page) so lower-volume events aren't
    cut off. This matters a lot: an UPCOMING game's prop menu ("- More Markets",
    "- Player Props") has far lower 24h volume than a LIVE game's, so with a
    small limit it falls past the cutoff and the upcoming game surfaces only its
    moneyline (a heavy favorite the payoff rule excludes) — i.e. no bettable
    props. Pulling deeper brings every game's full prop menu into view.
    """
    target = int(os.environ.get("EVENT_FETCH_LIMIT", str(limit or 200)))
    page = 100
    out, offset = [], 0
    while len(out) < target:
        params = {
            "closed": "false", "limit": str(page), "offset": str(offset),
            "order": "volume24hr", "ascending": "false", "tag_slug": tag_slug,
        }
        url = f"{GAMMA_BASE}/events?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read().decode("utf-8"))
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return out[:target]


def _as_list(raw):
    """Gamma returns outcomes / outcomePrices as JSON-encoded strings."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return []


def _to_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


_FAR_FUTURE = 9_999_999_999.0  # sorts undated markets last among "upcoming"


def _parse_ts(*candidates) -> float:
    """Parse the first valid timestamp into epoch seconds.

    Polymarket mixes formats: ISO with 'Z' and microseconds, but crucially
    gameStartTime looks like "2026-07-03 03:00:00+00" — a space separator and a
    short "+00" offset that datetime.fromisoformat rejects on older Pythons. If
    that fails to parse, a real FUTURE kickoff gets missed and the market looks
    long-finished (then the grace filter wrongly drops it). Normalize first.
    """
    for raw in candidates:
        if not raw or not isinstance(raw, str):
            continue
        s = raw.strip()
        if "T" not in s and " " in s:                     # "...03 03:00:00+00" -> "...03T03:00:00+00"
            s = s.replace(" ", "T", 1)
        s = s.replace("Z", "+00:00")
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)   # +0000 -> +00:00
        s = re.sub(r"([+-]\d{2})$", r"\1:00", s)          # +00   -> +00:00
        try:
            return datetime.fromisoformat(s).timestamp()
        except ValueError:
            continue
    return _FAR_FUTURE


def fetch_holders(condition_id: str, limit: int = 20) -> list:
    """Return the top holders per outcome token for a market, or [] on error."""
    params = {"market": condition_id, "limit": str(limit)}
    url = f"{DATA_BASE}/holders?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — never let one market kill the run
        print(f"  holders fetch failed for {condition_id[:10]}…: {exc}")
        return []


def fetch_sharp_traders(limit_per_page: int = 50, pages: int = 2) -> dict:
    """Fetch all-time most-profitable traders (SPORTS + OVERALL) by lifetime PnL.

    Returns {wallet_lower: {"pnl": float, "name": str, "rank": str}} — the set of
    historically 'sharp' wallets we weight more heavily when they show up as
    holders. Best-effort: returns {} on error.
    """
    sharp = {}
    for category in ("SPORTS", "OVERALL"):
        for page in range(pages):
            params = {
                "category": category, "timePeriod": "ALL", "orderBy": "PNL",
                "limit": str(limit_per_page), "offset": str(page * limit_per_page),
            }
            url = f"{DATA_BASE}/v1/leaderboard?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    rows = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                print(f"  leaderboard fetch failed ({category} p{page}): {exc}")
                continue
            for r in rows or []:
                wallet = (r.get("proxyWallet") or "").lower()
                if not wallet:
                    continue
                pnl = _to_float(r.get("pnl"))
                # Keep the best (highest-PnL) record if seen in multiple lists.
                if wallet not in sharp or pnl > sharp[wallet]["pnl"]:
                    sharp[wallet] = {
                        "pnl": pnl,
                        "name": r.get("userName") or wallet[:8],
                        "rank": r.get("rank", ""),
                    }
    print(f"Sharp traders loaded: {len(sharp)}")
    return sharp


def fetch_market_resolution(condition_id: str):
    """Return (closed, winning_outcome_name) for a market, or (False, None)."""
    if not condition_id:
        return (False, None)
    params = {"condition_ids": condition_id}
    url = f"{GAMMA_BASE}/markets?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        m = data[0] if isinstance(data, list) and data else data
        if not isinstance(m, dict) or not m.get("closed"):
            return (False, None)
        outcomes = _as_list(m.get("outcomes"))
        prices = [_to_float(p) for p in _as_list(m.get("outcomePrices"))]
        if outcomes and prices and len(outcomes) == len(prices):
            win_idx = max(range(len(prices)), key=lambda i: prices[i])
            return (True, outcomes[win_idx])
        return (True, None)
    except Exception:  # noqa: BLE001 — grading is best-effort
        return (False, None)

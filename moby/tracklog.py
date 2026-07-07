"""Signal tracking — append flagged signals to signals_log.jsonl."""
import json
import os

from moby.picks import flatten_picks


def _log_path() -> str:
    """signals_log.jsonl lives at the REPO ROOT (next to the moby.py shim),
    where the workflow's data-branch restore step puts it — not inside the
    package directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "signals_log.jsonl",
    )


def log_signals(result: dict, run_at: str, cid_by_market: dict) -> None:
    """Append each pick to signals_log.jsonl, enriched with condition_id so it
    can be graded (win/loss) on future runs."""
    log_path = _log_path()
    picks = flatten_picks(result)
    if not picks:
        return
    with open(log_path, "a") as f:
        for p in picks:
            cid = cid_by_market.get(p.get("market", ""), "")
            record = {
                "run_at": run_at,
                "market": p.get("market", ""),
                "smart_money_side": p.get("pick", ""),
                "conviction": p.get("conviction", ""),
                "tag": p.get("tag", "none"),
                "units": p.get("units"),
                "market_type": p.get("market_type", "other"),
                "condition_id": cid,
            }
            f.write(json.dumps(record) + "\n")
    print(f"Logged {len(picks)} pick(s) to signals_log.jsonl")


def commit_log() -> None:
    """Persistence of signals_log.jsonl is handled by the workflow, not here.

    Moby's log used to be committed straight to the default branch on every run
    (a stream of ``chore: log smart-money signals`` commits on ``main``). That
    conflicts with protecting ``main``, so persistence now lives in the CI
    workflow, which restores the log from the dedicated ``data`` branch before a
    run and force-pushes the updated log back to ``data`` after — keeping ``main``
    free of automated log commits. This function is intentionally a no-op; the
    run still writes ``signals_log.jsonl`` to disk via ``log_signals()``.
    """
    if os.path.exists(_log_path()):
        print("signals_log.jsonl written; persistence handled by the workflow's data-branch step")

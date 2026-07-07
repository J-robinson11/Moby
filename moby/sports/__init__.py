"""SPORTS registry + active-profile selection (MOBY_SPORTS env)."""
import os

from moby.sports.soccer import SOCCER
from moby.sports.wnba import WNBA
from moby.sports.ufc import UFC
from moby.sports.nfl import NFL
from moby.sports.nba import NBA

SPORTS = {
    SOCCER.key: SOCCER,
    WNBA.key: WNBA,
    UFC.key: UFC,
    NFL.key: NFL,
    NBA.key: NBA,
}


def get_profiles(env: str = None) -> list:
    """Return the active SportProfiles for MOBY_SPORTS (comma-separated keys,
    default "soccer"). Unknown keys are a startup error, not a silent skip —
    a half-registered sport must fail loudly before any network work."""
    raw = env if env is not None else os.environ.get("MOBY_SPORTS", "soccer")
    keys = [k.strip().lower() for k in raw.split(",") if k.strip()]
    if not keys:
        raise ValueError("MOBY_SPORTS is set but names no sports")
    unknown = [k for k in keys if k not in SPORTS]
    if unknown:
        raise ValueError(
            f"Unknown sport(s) in MOBY_SPORTS: {', '.join(unknown)} "
            f"(known: {', '.join(sorted(SPORTS))})"
        )
    return [SPORTS[k] for k in keys]

"""Shared test setup.

Puts the repo root on sys.path so `import moby` resolves whether pytest is run
from the root or elsewhere, and pins every tunable env knob to its documented
default so tests always exercise default behavior (env is read at call time
inside the functions, so a stray shell export would otherwise leak in).
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Every env knob moby reads at call time. Cleared per-test so defaults apply.
_KNOB_ENVS = (
    "EVENT_FETCH_LIMIT", "MARKET_CAP", "FUTURES_SLOTS",
    "MAX_GAME_PROPS_PER_GAME", "MAX_PLAYER_PROPS_PER_GAME",
    "WINDOW_HOURS", "NEXT_RUN_BUFFER_MIN", "LIVE_GRACE_MIN",
    "MIN_LIQUIDITY", "MAX_SPREAD", "MIN_SMART_MONEY_USD",
    "KELLY_FRACTION", "MAX_UNITS", "MAX_PICK_PRICE", "X_BEARER_TOKEN",
    "MOBY_SPORTS", "MARKET_TAG",
    "PREFILTER_TOP_N", "MODEL_SYNTH", "MODEL_NEWS", "ANTHROPIC_MODEL",
    "BATCH_MODE", "BATCH_WAIT_MIN", "NEWS_MAX_SEARCHES", "DRY_RUN",
)


@pytest.fixture(autouse=True)
def _default_knobs(monkeypatch):
    for k in _KNOB_ENVS:
        monkeypatch.delenv(k, raising=False)

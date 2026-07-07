"""The per-sport adapter contract.

A new sport = one small profile file + one channel webhook secret + one
registry entry in moby/sports/__init__.py — no core edits.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class SportProfile:
    key: str                 # "soccer" — env/log/CLI id
    label: str               # "World Cup" — Discord header + prompt subject
    market_tag: str          # Gamma tag_slug ("fifa-world-cup", "wnba", ...)
    webhook_env: str         # "DISCORD_WEBHOOK_URL_WNBA"; soccer → legacy "DISCORD_WEBHOOK_URL"
    game_strong: tuple       # classify hints: specific single-game market phrases
    player_hints: tuple      # classify hints: player-prop signals
    future_hints: tuple      # classify hints: season/tournament futures
    novelty: tuple           # junk markets to skip outright
    live_grace_min: int      # drop live games kicked off > this many mins ago
    sport_prompt: str        # in-play guidance blurb rendered into the prompt
    search_hints: str        # what the news search should chase for this sport
    defaults: dict = field(default_factory=dict)   # per-sport knob overrides (MIN_LIQUIDITY, ...)
    game_key: Optional[Callable] = None            # override event->game collapsing (UFC cards)
    classify: Optional[Callable] = None            # rare full classify override

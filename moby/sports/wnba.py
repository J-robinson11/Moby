"""WNBA — the reference adapter for the multi-sport architecture.

This is the first sport added after the Phase 0-4 rewrite, and the worked
example a new sport is copied from: one profile file, one channel webhook
secret, one registry entry in moby/sports/__init__.py — no core edits.

Ordering note (see markets.classify_market): game_strong is scanned against
"question + event" BEFORE player_hints. WNBA player props ALWAYS read
"... Over/Under N.5" ("A'ja Wilson: Points Over 21.5"), so bare "over "/
"under " in GAME_STRONG would swallow every player prop as a game_prop.
We therefore keep "over "/"under " OUT of GAME_STRONG and use compound
totals phrases ("total points over", "team total") instead; the stat words
("points", "rebounds", ...) live in PLAYER_HINTS and win the second pass.
"""
from moby.sports.base import SportProfile

# Specific single-game basketball market phrases. NO bare "over "/"under " here
# (they'd misclassify "Points Over 21.5" player props) — use compound totals.
GAME_STRONG = (
    "total points", "team total", "total points over", "total points under",
    "spread", "moneyline", "to win the game", "winning margin", "handicap",
    "race to", "double result", "overtime",
    "1st quarter", "first quarter", "2nd quarter", "second quarter",
    "3rd quarter", "third quarter", "4th quarter", "fourth quarter",
    "1st half", "first half", "2nd half", "second half", "halftime",
    "highest scoring", "both teams to score",
)
# Player-prop signals — checked against question AND event (player-prop events
# are titled e.g. "Aces vs. Liberty - Player Props"). Stat words go here, not in
# GAME_STRONG, so "... Over N.5" props land as player props not game props.
PLAYER_HINTS = (
    "points", "rebounds", "assists", "three-pointers", "3-pointers", "threes",
    "double-double", "triple-double", "steals", "blocks", "player prop",
    "to score", "pts+rebs", "points + rebounds", "first basket",
)
FUTURE_HINTS = (
    "champion", "winner", "mvp", "rookie of the year", "coach of the year",
    "most improved", "sixth", "defensive player", "scoring leader",
    # Bare "playoffs"/"postseason", not "make the playoffs": live phrasing is
    # "make the 2026 WNBA Playoffs" — words in between break compound hints.
    # Safe because in-season playoff GAME markets hit the "X vs Y" check first.
    "to win the finals", "playoffs", "postseason", "win the east",
    "win the west", "regular season", "to reach", "advance",
    "commissioner's cup",
)
# No junk/joke markets to blacklist for WNBA (yet).
NOVELTY = ()

# In-play guidance rendered into the analysis prompt (indentation matters:
# continuation lines sit inside the prompt's TIMING bullet).
SPORT_PROMPT = (
    "Live games are fair while there's meaningful time left (before ~midway\n"
    "    through the 4th quarter) — pick in-play markets that still hold value\n"
    "    (totals, spreads, race-to lines), not something already decided. A blowout\n"
    "    kills in-play value fast, so skip games that are out of reach."
)
SEARCH_HINTS = (
    "injuries/inactives, availability, back-to-backs and rest, recent form, and "
    "public lean for the relevant teams/players"
)

WNBA = SportProfile(
    key="wnba",
    label="WNBA",
    market_tag="wnba",
    webhook_env="DISCORD_WEBHOOK_URL_WNBA",
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=150,                  # ~2h game + OT, mirroring soccer's 105
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
    # WNBA liquidity is thinner than the World Cup; env still overrides (env >
    # defaults > global, per config.knob). WINDOW_HOURS stays at the global 18h
    # — WNBA plays a near-daily schedule, so same-day is the right horizon.
    defaults={
        "MIN_LIQUIDITY": "250",
        "MIN_SMART_MONEY_USD": "1000",
        "WINDOW_HOURS": "18",
    },
)

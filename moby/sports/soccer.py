"""World Cup / soccer — the original sport. Hint tuples and prompt blurbs are
the exact strings that lived in the single-file moby.py; markets.py imports
them back as its no-profile fallback so the legacy surface behaves identically.

An EPL/UCL profile later is a variant of this file with a different market_tag.
"""
from moby.sports.base import SportProfile

# Keyword hints for classifying a market by type. Lower number = scanned first.
# Specific single-match market phrases — win first so e.g. "both teams to score"
# isn't miscaught by the broad "to score" player hint.
GAME_STRONG = (
    "both teams to score", "btts", "total goals", "total corners", "corners",
    "over ", "under ", "exact score", "correct score", "halftime", "half-time",
    "1st half", "first half", "second half", "clean sheet", "first team to score",
    "to win the match", "end in a draw", "double chance", "handicap",
    "to score first", "winning margin", "anytime team",
)
# Player-prop signals — checked against question AND event (events are titled
# e.g. "Brazil vs. Japan - Player Props").
PLAYER_HINTS = (
    "to score", "goalscorer", "goal scorer", "golden boot", "top scorer",
    "hat trick", "hat-trick", "assist", "player prop", "anytime scorer",
    "first goal", "to be carded", "to be booked", "shots on target",
    "player to", " goals", "brace",
)
FUTURE_HINTS = (
    "win the world cup", "to win the tournament", "champion", "winner",
    "to reach", "reach the", "advance", "quarterfinal", "semifinal",
    "semi-final", "quarter-final", "to make the final", "reach final",
    "win group", "group winner", "to qualify", "round of 16", "round of 32",
    "golden glove", "golden ball", "furthest advancing",
)
# Novelty / joke markets with no real betting value — skip entirely so they
# don't eat slots (and tokens) meant for actual game props.
NOVELTY = ("announcers say", "what will the announcers")

# In-play guidance rendered into the analysis prompt (indentation matters:
# continuation lines sit inside the prompt's TIMING bullet).
SPORT_PROMPT = (
    "Live games are fair while there's meaningful time left (before ~75 min\n"
    "    played) — pick in-play markets that still hold value (next goal, total goals,\n"
    "    a team to score, comeback/draw lines), not something already decided."
)
SEARCH_HINTS = "news, form, injuries, lineups, and public lean for the relevant teams/players"

SOCCER = SportProfile(
    key="soccer",
    label="World Cup",
    market_tag="fifa-world-cup",
    webhook_env="DISCORD_WEBHOOK_URL",   # legacy webhook: soccer + ops/failure channel
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=105,                  # ~75 min played ≈ ~90 min wall clock + margin
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
)

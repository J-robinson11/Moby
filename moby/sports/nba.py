"""NBA — a near-clone of the WNBA reference (same basketball market structure),
with a fuller futures set for the men's league's tournaments and awards.

One profile file, one channel webhook secret, one registry entry in
moby/sports/__init__.py — no core edits.

Ordering note (see markets.classify_market): game_strong is scanned against
"question + event" BEFORE player_hints. NBA player props read
"LeBron James: Points O/U 27.5" — bare "over "/"under "/"o/u" in GAME_STRONG
would swallow every stat line as a game_prop. We keep bare over/under OUT of
GAME_STRONG (use compound totals like "total points"/"team total"), and put
the stat words ("points", "rebounds", ...) in PLAYER_HINTS so they win the
second pass. Same over/under rule as WNBA — see its module docstring.

Season note: it's the offseason when this ships — the live tag is dominated by
free-agency and roster speculation ("LeBron James Next Team", "retire before
next season", "traded"). Those correctly fall to "other" (they name no bettable
market type), and the pipeline's season gate keeps the sport dark; we do NOT
blacklist them.
"""
from moby.sports.base import SportProfile

# Specific single-game basketball phrases. NO bare "over "/"under "/"o/u" here
# (they'd misclassify "Points O/U 27.5" player props) — use compound totals.
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
# are titled e.g. "Lakers vs. Celtics - Player Props"). Stat words go here, not
# in GAME_STRONG, so "... O/U N.5" stat lines land as player props not game
# props.
PLAYER_HINTS = (
    "points", "rebounds", "assists", "three-pointers", "3-pointers", "threes",
    "double-double", "triple-double", "steals", "blocks", "player prop",
    "to score", "pts+rebs", "points + rebounds", "first basket",
)
# Season/tournament futures — WNBA's set plus the men's-league extras.
FUTURE_HINTS = (
    "champion", "winner", "mvp", "finals", "nba cup", "in-season tournament",
    "play-in", "rookie of the year", "coach of the year", "most improved",
    "sixth", "defensive player", "scoring leader",
    "playoffs", "postseason", "to win the finals",
    "conference", "win the east", "win the west", "win total",
    "regular season", "no. 1 seed", "number 1 seed", "first overall pick",
    "draft", "to reach", "advance",
)
# No junk/joke markets to blacklist for NBA (yet).
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

NBA = SportProfile(
    key="nba",
    label="NBA",
    market_tag="nba",
    webhook_env="DISCORD_WEBHOOK_URL_NBA",
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=150,                  # ~2h game + OT, mirroring WNBA
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
    # NBA regular-season liquidity is deep, but stays conservative like WNBA;
    # env still overrides (env > defaults > global, per config.knob).
    # WINDOW_HOURS stays 18h — the NBA plays a near-daily schedule.
    defaults={
        "MIN_LIQUIDITY": "250",
        "MIN_SMART_MONEY_USD": "1000",
        "WINDOW_HOURS": "18",
    },
)

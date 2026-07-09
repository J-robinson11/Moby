"""NFL — the football adapter, structured like the WNBA reference.

One profile file, one channel webhook secret, one registry entry in
moby/sports/__init__.py — no core edits.

Ordering note (see markets.classify_market): game_strong is scanned against
"question + event" BEFORE player_hints. NFL player props read
"Patrick Mahomes: Passing Yards O/U 275.5" — bare "over "/"under "/"o/u" in
GAME_STRONG would swallow every stat line as a game_prop. We therefore keep
bare over/under OUT of GAME_STRONG (use compound totals like "total points"/
"team total"), and put the stat words ("passing yards", "receptions", ...) in
PLAYER_HINTS so they win the second pass.

Futures collision to keep in mind (has a regression test): a season
"win total over 9.5" market must land as FUTURE, not game_prop. Because bare
"over" is NOT in GAME_STRONG, no game_strong phrase fires, no player stat fires,
there is no "X vs Y", and finally "win total" in FUTURE_HINTS catches it.

Season note: it's the offseason when this ships — the live tag is mostly
futures + roster speculation ("Where will Tyreek Hill play next?", "retire",
"traded"). Those correctly fall to "other" (they name no bettable market type),
and the pipeline's season gate keeps the sport dark; we do NOT blacklist them.
Game/player phrasings below are validated against Polymarket's in-season
conventions ("Chiefs vs. Ravens: O/U 47.5", "Spread: Chiefs (-3.5)").
"""
from moby.sports.base import SportProfile

# Specific single-game football phrases. NO bare "over "/"under "/"o/u" here
# (they'd misclassify "Passing Yards O/U 275.5" player props) — use compound
# totals and the game-market vocabulary.
GAME_STRONG = (
    "total points", "team total", "total points over", "total points under",
    "spread", "moneyline", "to win the game", "winning margin", "handicap",
    "race to", "overtime", "first score", "first team to score", "first td of the game",
    "1st quarter", "first quarter", "2nd quarter", "second quarter",
    "3rd quarter", "third quarter", "4th quarter", "fourth quarter",
    "1st half", "first half", "2nd half", "second half", "halftime",
    "highest scoring", "both teams to score", "field goal",
)
# Player-prop signals — checked against question AND event (player-prop events
# are titled e.g. "Chiefs vs. Ravens - Player Props"). Stat words go here, not in
# GAME_STRONG, so "... O/U N.5" stat lines land as player props not game props.
PLAYER_HINTS = (
    "passing yards", "rushing yards", "receiving yards", "receptions",
    "pass yards", "rush yards", "rec yards", "touchdown", "touchdowns",
    "anytime td", "first td", "longest reception", "longest rush",
    "interceptions", "sacks", "completions", "to score", "longest",
    "player prop", "passing tds", "rushing tds",
)
# Season/tournament futures.
FUTURE_HINTS = (
    "super bowl", "champion", "mvp", "playoffs", "postseason", "division",
    "win total", "regular season", "rookie of the year", "offensive player",
    "defensive player", "coach of the year", "to reach", "advance",
    "conference", "win the afc", "win the nfc", "afc championship",
    "nfc championship", "no. 1 seed", "number 1 seed", "first overall pick",
    "draft", "undefeated",
)
# The Super Bowl "halftime show" performer market is a recurring entertainment
# market with no football betting value — and its title collides with the real
# game hint "halftime" (game-half markets). Blacklist it so it's skipped
# outright rather than misfiled as a game prop.
NOVELTY = ("halftime show", "perform at the")

# In-play guidance rendered into the analysis prompt (indentation matters:
# continuation lines sit inside the prompt's TIMING bullet).
SPORT_PROMPT = (
    "Live games are fair while there's meaningful time left (before ~midway\n"
    "    through the 4th quarter) — pick in-play markets that still hold value\n"
    "    (totals, spreads, race-to lines, next score), not something already\n"
    "    decided. A blowout kills in-play value fast, so skip games out of reach."
)
SEARCH_HINTS = (
    "injuries/inactives and questionable tags, snap counts and usage, weather, "
    "recent form, and public lean for the relevant teams/players"
)

NFL = SportProfile(
    key="nfl",
    label="NFL",
    market_tag="nfl",
    webhook_env="DISCORD_WEBHOOK_URL_NFL",
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=210,                  # ~3.5h game
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
    # Games cluster Thu/Sun/Mon with the big Sunday slate; 48h lets Friday and
    # Saturday runs preview Sunday (where lines move most) instead of only
    # catching games same-day. Env WINDOW_HOURS still wins.
    defaults={"WINDOW_HOURS": "48"},
)

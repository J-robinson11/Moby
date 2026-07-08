"""MLB — the volume sport.

Live-validated against the Polymarket "mlb" tag on 2026-07-08: 198 events /
4,094 markets — the largest board of any adapter (WNBA was 599). Baseball's
problem isn't classification, it's LADDERS: one game carries a totals ladder
(O/U 6.5 ... 17.5), a spread ladder (-1.5 ... -5.5), 1st-5-innings versions of
both, and 2 home-run props per batter. Left at the global per-game caps
(30 game / 15 player), three games' ladders would eat the whole 100-market
candidate cap — so this profile's real work is in ``defaults``.

Ordering note (see markets.classify_market): stat-line player props read
"Colby Thomas: Home Runs O/U 0.5", so bare "o/u"/"over "/"under " must stay
OUT of GAME_STRONG. Game totals ("Brewers vs. Cardinals: O/U 7.5") carry no
keyword at all and are caught by the " vs " fallback AFTER player hints —
which is safe because no stat word appears in a team-totals question.
"""
from moby.sports.base import SportProfile

# Single-game baseball market phrases. Live phrasings: "Spread: Milwaukee
# Brewers (-1.5)", "1st 5 Innings Spread: ...", "... : 1st 5 Innings O/U 3.5",
# "Will there be a run scored in the first inning?: X vs. Y", "Will the game
# go to extra innings?: X vs. Y". NO bare "o/u"/"over"/"under" here.
GAME_STRONG = (
    "spread", "moneyline", "run line", "runline", "team total",
    "1st 5 innings", "first 5 innings", "first five innings",
    "extra innings", "first inning", "1st inning",
    "to win the game", "winning margin", "race to",
    "both teams to score", "grand slam in the game",
)
# Player-prop stat words — "Name: Home Runs O/U 0.5", "Name: Strikeouts
# O/U 6.5", "Name: Total Bases O/U 1.5". Compound "<stat> o/u" forms where a
# bare word would be ambiguous; bare words where baseball only uses them for
# players (nobody writes a game market containing "strikeouts").
PLAYER_HINTS = (
    "home run", "strikeout", "total bases", "rbi", "stolen base",
    "hits o/u", "hits over", "hits under", "singles o/u", "doubles o/u",
    "triples o/u", "walks o/u", "earned runs", "outs recorded",
    "pitching outs", "hits allowed", "to record a hit", "to hit a",
    "to record a win", "batter", "pitcher", "player prop", "to score a run",
    "first career",
)
FUTURE_HINTS = (
    "world series", "pennant", "mvp", "cy young", "rookie of the year",
    "manager of the year", "gold glove", "platinum glove", "silver slugger",
    "batting title", "award", "all-star", "hall of fame",
    # Bare "playoffs"/"postseason"/"division"/"wild card" per the WNBA lesson:
    # live phrasing splices season years into compound hints ("make the 2026
    # MLB Playoffs"). Safe: in-season game markets hit the vs-check first.
    "playoffs", "postseason", "division", "wild card",
    "regular season", "season wins", "to make the", "to reach", "advance",
    "champion", "winner", "leader", "no-hitter thrown", "perfect game",
    "winning streak", "losing streak",
    "triple crown", "40/40", "50 home runs", "60 home runs",
)
# Front-office gossip, not betting signal (live check 2026-07-08: ~700 draft
# markets + ~140 "next manager" ladders on the tag). Blacklisted like the NFL
# halftime show — dropped before holder calls, so they cost nothing and can't
# crowd the FUTURES_SLOTS meant for World Series/award odds.
# "be the next" (not "next manager") because live phrasing splices the team
# in: "be the next RED SOX manager" — the same compound-hint lesson as WNBA's
# "make the 2026 WNBA Playoffs".
NOVELTY = ("mlb draft", "be drafted", "be the next", "permanent manager",
           "next gm", "general manager")

# In-play guidance (indentation matters: continuation lines sit inside the
# prompt's TIMING bullet).
SPORT_PROMPT = (
    "Live games are fair while there's meaningful game left (before ~the 7th\n"
    "    inning) — prefer in-play markets whose question is still genuinely open\n"
    "    (full-game totals, run lines; 1st-5-innings lines are DEAD once the 5th\n"
    "    ends). Watch the pitching change: a starter exiting flips run-scoring\n"
    "    dynamics, and a blowout kills in-play value fast. With ~15 games a day,\n"
    "    be selective — surface only the games where the smart-money signal is\n"
    "    clearest, not something from every slate."
)
SEARCH_HINTS = (
    "probable starting pitchers and matchup history, injuries/IL moves, "
    "confirmed lineups, bullpen usage the last few days, weather/wind at the "
    "ballpark, and public lean for the relevant teams/players"
)

MLB = SportProfile(
    key="mlb",
    label="MLB",
    market_tag="mlb",
    webhook_env="DISCORD_WEBHOOK_URL_MLB",
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=200,                  # ~3h game; soccer 105, wnba 150
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
    # The volume knobs — the reason this profile exists (env still overrides):
    # ~15 games/day with deep ladders means per-game caps decide whether the
    # 100-market candidate cap holds 3 games or 12. Tight per-game slices keep
    # every slate's best number represented instead of one game's whole ladder.
    defaults={
        "MAX_GAME_PROPS_PER_GAME": "8",   # ML + best spreads + 2-3 totals + a 1st-5
        "MAX_PLAYER_PROPS_PER_GAME": "6", # the sharpest props, not 2 per batter
    },
)

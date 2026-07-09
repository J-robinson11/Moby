"""UFC — the fight-sport adapter, structured like the WNBA reference but with
combat-specific market phrasing.

One profile file, one channel webhook secret, one registry entry in
moby/sports/__init__.py — no core edits.

Ordering note (see markets.classify_market): game_strong is scanned against
"question + event" BEFORE player_hints. A fight's winner market lives in an
event titled "UFC 329: Max Holloway vs. Conor McGregor (...)", so the bare
"X vs. Y" fallback catches it as a game_prop. The per-fight market menu is
method-of-victory ("Will the fight be won by KO or TKO?", "Fight to Go the
Distance?"), round totals ("O/U 2.5 Rounds") and per-fighter method lines
("Will Conor McGregor win by KO or TKO?") — all game-level fight markets, so
they go in GAME_STRONG. Round totals read "O/U N.5 Rounds", so we key on the
compound "rounds" phrasing, NOT bare "over "/"under "/"o/u", which would be
noise (there are no stat-line player props here to protect, but keeping the
rule consistent with the stat-line sports avoids surprises).

game_key note: fight/card event titles never contain " - " (they read
"UFC 329: A vs. B (Weight, Card)"), so the default _game_key split on " - "
is a harmless no-op — each fight is already its own event and its own key.
We therefore leave game_key=None; there is no multi-event-per-fight collapse
to do the way soccer has "... - Player Props"/"... - Exact Score".

Liquidity note: live fight-market liquidity is thin (median ≈ $47, far below
World Cup levels), so we set the same conservative floors WNBA uses.
"""
from moby.sports.base import SportProfile

# Specific single-fight market phrases. Method-of-victory + round totals are all
# GAME-level fight markets (they resolve on how/when THE fight ends), so they
# belong here and win the first pass. Round totals read "O/U N.5 Rounds", so we
# key on "rounds"/"round " — NOT bare "over "/"under "/"o/u".
GAME_STRONG = (
    "method of victory", "by ko", "ko or tko", "ko/tko", "by tko",
    "by submission", "by decision", "go the distance", "inside the distance",
    "total rounds", "rounds", "round 1", "round 2", "round 3", "in round",
    "which round", "to win by", "fight to go", "win by ko", "win by submission",
)
# Per-fighter STAT props (contract requires non-empty). Live UFC props are
# sparse right now, but these are the standard fighter-stat lines and stay clear
# of the method markets above; stat words go here so any "... Over N.5" stat
# line lands as a player prop, not a game prop.
PLAYER_HINTS = (
    "takedown", "takedowns", "knockdown", "knockdowns", "significant strikes",
    "sig strikes", "strikes landed", "point deduction", "control time",
    "player prop", "fighter prop", "to land",
)
# Season/belt futures. The live tag carries three career-speculation families:
# belt/title outlook ("... Champion on December 31"), ranking outlook ("next
# fighter to be ranked first"/"remain #1"), and next-opponent ("Who will X fight
# next?"). We route ALL of them to "future" — they name a concrete future
# outcome a smart-money model can price ("next fight"/"fight next"/"next fighter"
# cover both title-phrasings of the opponent markets). The only thing left in
# "other" is the pure will-he-even-compete question ("Will Conor McGregor Fight
# in 2026?"), which names no outcome to price. "to remain"/"vacate" cover
# belt-holding.
FUTURE_HINTS = (
    "champion", "title", "belt", "to fight next", "fight next", "next fight",
    "to remain", "remain #1", "vacate", "pound-for-pound", "pound for pound",
    "p4p", "ranked first", "next fighter", "grand prix", "tournament",
    "become a ufc champion",
)
# No junk/joke markets to blacklist for UFC (yet).
NOVELTY = ()

# In-play guidance rendered into the analysis prompt (indentation matters:
# continuation lines sit inside the prompt's TIMING bullet).
SPORT_PROMPT = (
    "A fight is live for only a few minutes at a time — a card runs for hours,\n"
    "    so a fight-level market (method of victory, round totals, the winner) is\n"
    "    fair until that specific bout is underway or over. Skip markets on fights\n"
    "    that have already finished on the card; chase the ones still to come."
)
SEARCH_HINTS = (
    "weigh-in results and misses, injuries/withdrawals and short-notice "
    "replacements, camp/style matchups, and public lean for the relevant fighters"
)

UFC = SportProfile(
    key="ufc",
    label="UFC",
    market_tag="ufc",                    # verified live: richer than "mma"
    webhook_env="DISCORD_WEBHOOK_URL_UFC",
    game_strong=GAME_STRONG,
    player_hints=PLAYER_HINTS,
    future_hints=FUTURE_HINTS,
    novelty=NOVELTY,
    live_grace_min=300,                  # a full card runs ~5h; the market clock
                                         # covers the whole card window
    sport_prompt=SPORT_PROMPT,
    search_hints=SEARCH_HINTS,
    # Fight-market liquidity is thin (median ≈ $47 live); env still overrides
    # (env > defaults > global, per config.knob). WINDOW_HOURS=96 wakes UFC on
    # fight week (cards run ~weekly, usually Saturday; a Tuesday card is ~93h
    # out) so early sharp money on a fight surfaces days ahead, not fight-day.
    defaults={
        "MIN_LIQUIDITY": "250",
        "MIN_SMART_MONEY_USD": "1000",
        "WINDOW_HOURS": "96",
    },
    # Fight events are already one-per-fight and never carry a " - " suffix, so
    # the default _game_key is a harmless no-op — no override needed.
    game_key=None,
)

"""THE guarantee of the refactor: byte-exact Discord payloads.

The golden fixtures pin "_run_slot" (build_discord_payload falls back to the
time-dependent run_slot_label() without it) so the payload is fully
deterministic. `*_result.json` is the model-result input; `*_payload.json` is
the exact JSON (indent=2, sort_keys=True) the current renderer produces. Any
refactor that changes a single byte of soccer output fails here.

Regenerate (ONLY for a deliberate, user-approved format change):
    python tests/fixtures/regenerate_golden.py
"""
import json
import os

import pytest

import moby

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
GOLDEN_NAMES = ("golden_full_slate", "golden_no_picks")


def _read(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def canonical_json(payload) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_payload_byte_exact(name):
    result = json.loads(_read(f"{name}_result.json"))
    payload = moby.build_discord_payload(result)
    assert canonical_json(payload) == _read(f"{name}_payload.json"), (
        f"Discord payload drifted from golden fixture {name}_payload.json"
    )


# --- Ported render smoke asserts (from the old ci.yml heredoc) --------------

def _full_slate():
    return {"picks": {
        "game_props": [{
            "market": "Argentina vs Brazil — total goals over 2.5",
            "pick": "Over 2.5", "conviction": "High", "kickoff": "2026-06-29T18:00:00Z",
            "smart_money": "72% of $45k on Over", "news": "Both teams attacking form.",
            "rationale": "Big money + news agree.", "contrarian_note": "Defensive history.",
            "tag": "contrarian", "tag_note": "sharp Over vs raw Under",
        }],
        "player_props": [{"market": "Messi to score", "pick": "Yes", "conviction": "Medium"}],
        "futures": [],
    }, "summary": "Two plays today.", "_track_record": {"note": "3/4 won (75%)."},
       "_run_slot": "5:00 PM"}


def test_no_pick_payload_has_title():
    parsed = {"picks": {"game_props": [], "player_props": [], "futures": []},
              "watchlist": ["USA props"], "summary": "Quiet."}
    no_pick = moby.build_discord_payload(parsed)
    assert no_pick["embeds"][0]["title"]


def test_payload_never_ships_empty_fields():
    # Discord rejects empty field values.
    full = _full_slate()
    flat = moby.flatten_picks(full)
    assert len(flat) == 2 and flat[0]["bucket"] == "game_props", flat
    payload = moby.build_discord_payload(full)
    for embed in payload["embeds"]:
        for field in embed.get("fields", []):
            assert field["value"] != "", f"empty field: {field['name']}"


def test_tagged_pick_gets_badge_and_role_line():
    # A tagged pick gets a badge in its title AND a "Role" line; untagged picks
    # get neither (layout otherwise unchanged).
    payload = moby.build_discord_payload(_full_slate())
    tagged = next(e for e in payload["embeds"] if "CONTRARIAN" in e.get("title", ""))
    assert any(f["name"] == "Role" for f in tagged["fields"]), tagged
    assert "Contrarian" in next(f["value"] for f in tagged["fields"] if f["name"] == "Role")
    plain = next(e for e in payload["embeds"] if "Messi" in e.get("description", ""))
    assert not any(f["name"] == "Role" for f in plain["fields"]), plain
    assert "CONTRARIAN" not in plain["title"] and "HEDGE" not in plain["title"]


def test_sport_label_prefixes_header_full_slate():
    # With _sport_label the header gains the "· {label}" prefix; without it the
    # original single-sport title stands, byte-for-byte.
    base = _full_slate()
    plain = moby.build_discord_payload(base)["embeds"][0]["title"]
    assert plain == "🐋 Moby — 5:00 PM run"
    labeled = moby.build_discord_payload({**base, "_sport_label": "WNBA"})["embeds"][0]["title"]
    assert labeled == "🐋 Moby · WNBA — 5:00 PM run"


def test_sport_label_prefixes_header_no_picks():
    base = {"picks": {"game_props": [], "player_props": [], "futures": []},
            "watchlist": ["USA props"], "summary": "Quiet.", "_run_slot": "7:00 AM"}
    plain = moby.build_discord_payload(base)["embeds"][0]["title"]
    assert plain == "🐋 Moby — 7:00 AM run · no bets"
    labeled = moby.build_discord_payload({**base, "_sport_label": "WNBA"})["embeds"][0]["title"]
    assert labeled == "🐋 Moby · WNBA — 7:00 AM run · no bets"


def test_embed_count_capped_at_discord_limit():
    many = {"picks": {"game_props": [
        {"market": f"Game {i} total goals", "pick": "Over", "conviction": "Low", "price": 0.5}
        for i in range(15)
    ], "player_props": [], "futures": []}, "summary": "Busy day.", "_run_slot": "5:00 PM"}
    payload = moby.build_discord_payload(many)
    assert len(payload["embeds"]) == 10  # Discord max 10 embeds (header + 9 picks)

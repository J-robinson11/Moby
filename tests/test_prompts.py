"""Prompt-drift guarantee: the rendered soccer prompt is STRING-EQUAL to the
original single-file ANALYSIS_INSTRUCTIONS (captured as a fixture before the
template was introduced)."""
import os

import moby
from moby.prompts import ANALYSIS_INSTRUCTIONS, render_instructions
from moby.sports import SPORTS
from moby.sports.soccer import SOCCER

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _original() -> str:
    with open(os.path.join(FIXTURES, "analysis_instructions_soccer.txt")) as f:
        return f.read()


def test_rendered_soccer_prompt_verbatim():
    assert render_instructions(SOCCER) == _original()


def test_legacy_constant_still_the_soccer_prompt():
    assert ANALYSIS_INSTRUCTIONS == _original()
    assert moby.ANALYSIS_INSTRUCTIONS == _original()


def test_no_unrendered_slots_for_any_sport():
    for profile in SPORTS.values():
        text = render_instructions(profile)
        assert "<<" not in text and ">>" not in text, profile.key

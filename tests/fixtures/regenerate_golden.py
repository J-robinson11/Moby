#!/usr/bin/env python3
"""Regenerate the golden Discord payload fixtures from the CURRENT renderer.

ONLY run this for a deliberate, user-approved output-format change (e.g. the
Phase-4 multi-sport header). Regenerating to make a red golden test pass
defeats the entire point of the fixture.
"""
import json
import os
import sys

FIXTURES = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(FIXTURES)))

import moby  # noqa: E402

for name in ("golden_full_slate", "golden_no_picks"):
    with open(os.path.join(FIXTURES, f"{name}_result.json")) as f:
        result = json.load(f)
    payload = moby.build_discord_payload(result)
    out_path = os.path.join(FIXTURES, f"{name}_payload.json")
    with open(out_path, "w") as f:
        f.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"{name}: {len(payload['embeds'])} embeds -> {out_path}")

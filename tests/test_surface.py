"""The module imports cleanly and the full public surface exists.

After the Phase-1 package split, `moby/__init__.py` must keep re-exporting all
of these so `import moby; moby.clean_markets(...)` keeps working.
"""
import moby

PUBLIC_SURFACE = (
    "clean_markets", "summarize_holders", "parse_json_block",
    "build_discord_payload", "send_alert", "log_signals",
    "flatten_picks", "load_track_record", "fetch_x_sentiment",
    "fetch_sharp_traders", "sharp_weight", "run_slot_label",
    "prune_low_upside", "annotate_contrarian", "next_scheduled_run",
    "suggest_units", "annotate_units",
)


def test_public_surface_present():
    for fn in PUBLIC_SURFACE:
        assert hasattr(moby, fn), f"missing function: {fn}"

"""Run-slot labeling and next-run window boundaries (Central 7AM/12PM/5PM)."""
from datetime import datetime, timezone

import moby


def test_run_slot_label_snaps_to_clean_central_slot():
    # Drifted run times snap to clean Central slots.
    assert moby.run_slot_label(datetime(2026, 6, 29, 22, 30, tzinfo=timezone.utc)) == "5:00 PM"


def test_next_run_keyed_to_current_slot_not_next_after_now():
    # Next-run boundary = the run AFTER the CURRENT one (keyed to the current
    # slot, not "next slot after now"). From 12 PM CT the next run is 5 PM;
    # after 5 PM CT it's next-day 7 AM.
    assert moby.next_scheduled_run(datetime(2026, 6, 29, 17, 0, tzinfo=timezone.utc))[1] == "5:00 PM"
    assert moby.next_scheduled_run(datetime(2026, 6, 29, 23, 0, tzinfo=timezone.utc))[1] == "7:00 AM"


def test_next_run_from_early_cron_fire():
    # CRITICAL: the 5 PM cron fires at 16:20 CT (21:20 UTC). Its next run must
    # be next-day 7 AM (a ~14h window covering the evening), NOT 5 PM itself —
    # otherwise the evening's games get wrongly excluded from the window.
    assert moby.next_scheduled_run(datetime(2026, 6, 29, 21, 20, tzinfo=timezone.utc))[1] == "7:00 AM"
    # 12 PM cron fires 11:20 CT (16:20 UTC) -> next run is 5 PM (a ~5h window).
    assert moby.next_scheduled_run(datetime(2026, 6, 29, 16, 20, tzinfo=timezone.utc))[1] == "5:00 PM"


def test_next_run_timestamp_is_true_utc():
    ts_5pm, _ = moby.next_scheduled_run(datetime(2026, 6, 29, 22, 0, tzinfo=timezone.utc))  # 5 PM CT
    assert ts_5pm == datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc).timestamp()  # 7 AM CT next day


def test_run_slot_label_correct_after_dst_ends():
    # After DST ends (Nov 1, 2026) Central = UTC-6 (CST). 15:00 UTC is 9:00 AM
    # CST -> nearest slot 7 AM. The old hardcoded UTC-5 read it as 10:00 AM and
    # mislabeled the run "12:00 PM".
    assert moby.run_slot_label(datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc)) == "7:00 AM"


def test_next_run_timestamp_correct_after_dst_ends():
    # 23:00 UTC = 5:00 PM CST -> next run is next-day 7 AM CST = 13:00 UTC.
    # The old UTC-5 math returned 12:00 UTC, an hour early.
    ts, label = moby.next_scheduled_run(datetime(2026, 11, 15, 23, 0, tzinfo=timezone.utc))
    assert label == "7:00 AM"
    assert ts == datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc).timestamp()

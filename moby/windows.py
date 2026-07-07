"""Run-slot labeling and window boundaries (Central 7AM / 12PM / 5PM slots).

Central time comes from zoneinfo("America/Chicago"), so CDT/CST is handled
automatically — the old hardcoded UTC-5 was only correct while DST held and
would have drifted an hour after Nov 1.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_CENTRAL = ZoneInfo("America/Chicago")


def run_slot_label(now_utc: datetime = None) -> str:
    """Label the run by its nearest scheduled Central slot, e.g. '5:00 PM'.

    The cron fires ~7:20a / 12:20p / 5:20p CT (with GitHub drift); we snap to the
    clean 7AM / 12PM / 5PM slot.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    ct = now_utc.astimezone(_CENTRAL)
    hr = ct.hour + ct.minute / 60.0
    nearest = min((7, 12, 17), key=lambda s: abs(s - hr))
    ampm = "AM" if nearest < 12 else "PM"
    h12 = nearest if nearest <= 12 else nearest - 12
    return f"{h12}:00 {ampm}"


_RUN_SLOTS_CT = (7, 12, 17)  # Central hours of the 3 daily runs
_SLOT_LABELS = {7: "7:00 AM", 12: "12:00 PM", 17: "5:00 PM"}


def next_scheduled_run(now_utc: datetime = None):
    """Return (utc_timestamp, label) of the run AFTER the current one — i.e. the
    boundary of THIS run's window (Central 7AM/12PM/5PM).

    Keyed to the CURRENT run's slot (nearest slot, matching run_slot_label), not
    merely "the next slot after now." That distinction matters: GitHub's cron for
    the 5PM run fires at 16:20 CT, so "next slot after now" would pick 5PM itself
    and shrink the window to ~40min — wrongly excluding that whole evening's
    games. The slot is built as a Central wall-clock time; .timestamp() resolves
    the true UTC offset (CDT or CST) for that date.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    ct = now_utc.astimezone(_CENTRAL)
    hr = ct.hour + ct.minute / 60.0
    current = min(_RUN_SLOTS_CT, key=lambda s: abs(s - hr))   # this run's slot
    idx = _RUN_SLOTS_CT.index(current)
    if idx + 1 < len(_RUN_SLOTS_CT):
        nxt_h, day = _RUN_SLOTS_CT[idx + 1], 0
    else:
        nxt_h, day = _RUN_SLOTS_CT[0], 1                      # after the last slot -> next day's first
    slot = ct.replace(hour=nxt_h, minute=0, second=0, microsecond=0) + timedelta(days=day)
    return (slot.timestamp(), _SLOT_LABELS[nxt_h])

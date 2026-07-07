"""Alert dispatch: Discord webhook → ntfy → Twilio SMS (checked in that order)."""
import os

import requests

from moby.picks import flatten_picks
from moby.render import _BUCKET_LABEL, build_discord_payload


def send_alert(result: dict) -> None:
    """Send the alert via whichever channel is configured (free options first)."""
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        payload = build_discord_payload(result)
        r = requests.post(os.environ["DISCORD_WEBHOOK_URL"], json=payload, timeout=30)
        r.raise_for_status()
        print("Alert sent via Discord webhook.")
        return

    picks = flatten_picks(result)
    summary = result.get("summary", "")
    if not picks:
        body = f"Moby: no bets on today's slate. {summary}"
    else:
        top = picks[0]
        extra = f" (+{len(picks) - 1} more)" if len(picks) > 1 else ""
        body = (
            f"Moby slate: [{_BUCKET_LABEL.get(top['bucket'], '')}] {top.get('pick')} — "
            f"{top.get('market')} ({top.get('conviction')} conviction){extra}. "
            f"Not financial advice."
        )[:600]

    if os.environ.get("NTFY_TOPIC"):
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        r = requests.post(
            f"{server}/{os.environ['NTFY_TOPIC']}",
            data=body.encode("utf-8"),
            headers={"Title": "Moby smart-money", "Priority": "high", "Tags": "whale"},
            timeout=30,
        )
        r.raise_for_status()
        print("Alert sent via ntfy.")
        return

    if os.environ.get("TWILIO_ACCOUNT_SID"):
        sid = os.environ["TWILIO_ACCOUNT_SID"]
        token = os.environ["TWILIO_AUTH_TOKEN"]
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        r = requests.post(
            url,
            data={"From": os.environ["TWILIO_FROM"], "To": os.environ["ALERT_TO_PHONE"], "Body": body},
            auth=(sid, token),
            timeout=30,
        )
        r.raise_for_status()
        print(f"SMS sent, Twilio SID: {r.json().get('sid')}")
        return

    raise RuntimeError(
        "No alert channel configured. Set DISCORD_WEBHOOK_URL, NTFY_TOPIC, or "
        "the four TWILIO_* / ALERT_TO_PHONE variables."
    )

"""
Membership plans + daily command quotas.

Plans:
  free      — 3 commands/day, 1 reminder, 3 saved recordings
  monthly   — 50 commands/day
  supermax  — 100 commands/day

A "command" is one functional action: a photo/picture/document upload
(translate + read), a web-page read, or an assistant message. The reminder and
recording caps are enforced on-device (they're stored client-side); the daily
command quota is enforced here, server-side, so it can't be bypassed.
"""

import json
from datetime import datetime, timezone

from flask import Response

PLAN_LIMITS = {
    "free":     {"daily": 3,    "reminders": 1,     "recordings": 3,     "label": "Free"},
    "monthly":  {"daily": 50,   "reminders": 99999, "recordings": 99999, "label": "Monthly"},
    "supermax": {"daily": 100,  "reminders": 99999, "recordings": 99999, "label": "Super Max"},
}
DEFAULT_PLAN = "free"


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def effective_plan(user):
    """The plan that's actually in force — a paid plan past its expiry is free."""
    plan = (getattr(user, "plan", None) or DEFAULT_PLAN)
    if plan not in PLAN_LIMITS:
        plan = DEFAULT_PLAN
    until = getattr(user, "plan_until", None)
    if plan != "free" and until is not None and until < datetime.utcnow():
        return "free"
    return plan


def _used_today(user):
    if getattr(user, "usage_day", "") != _today():
        return 0
    return int(getattr(user, "usage_count", 0) or 0)


def snapshot(user):
    plan = effective_plan(user)
    lim = PLAN_LIMITS[plan]
    used = _used_today(user)
    return {
        "plan": plan,
        "plan_label": lim["label"],
        "daily_limit": lim["daily"],
        "used_today": used,
        "remaining": max(0, lim["daily"] - used),
        "reminders_limit": lim["reminders"],
        "recordings_limit": lim["recordings"],
    }


def consume(user, n=1):
    """Count `n` commands against today's allowance.

    Returns (ok, snapshot). When the day rolls over the counter resets. If the
    user is already at the limit nothing is charged and ok is False.
    """
    today = _today()
    if getattr(user, "usage_day", "") != today:
        user.usage_day = today
        user.usage_count = 0
    lim = PLAN_LIMITS[effective_plan(user)]
    if int(user.usage_count or 0) >= lim["daily"]:
        return False, snapshot(user)
    user.usage_count = int(user.usage_count or 0) + n
    user.save()
    return True, snapshot(user)


def quota_response(snap):
    """The 402 returned to a client that's out of commands for the day."""
    return Response(json.dumps({
        "message": (f"You've used all {snap['daily_limit']} of today's commands on the "
                    f"{snap['plan_label']} plan. Upgrade for more, or try again tomorrow."),
        "quota_exceeded": True,
        "usage": snap,
    }), status=402, mimetype="application/json")

"""
Membership plans + daily command quotas.

Plans (command allowance resets monthly):
  free      — 3 commands/month, 1 reminder, 3 saved recordings
  monthly   — 50 commands/month
  supermax  — 100 commands/month

A "command" is one functional action: a photo/picture/document upload
(translate + read), a web-page read, or an assistant message. The reminder and
recording caps are enforced on-device (they're stored client-side); the monthly
command quota is enforced here, server-side, so it can't be bypassed.
"""

import json
from datetime import datetime, timezone

from flask import Response

PLAN_LIMITS = {
    "free":     {"monthly": 3,    "reminders": 1,     "recordings": 3,     "label": "Free"},
    "monthly":  {"monthly": 50,   "reminders": 99999, "recordings": 99999, "label": "Monthly"},
    "supermax": {"monthly": 100,  "reminders": 99999, "recordings": 99999, "label": "Super Max"},
}
DEFAULT_PLAN = "free"


def _period():
    """Current quota period — a calendar month, e.g. '2026-06'."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def effective_plan(user):
    """The plan that's actually in force — a paid plan past its expiry is free."""
    plan = (getattr(user, "plan", None) or DEFAULT_PLAN)
    if plan not in PLAN_LIMITS:
        plan = DEFAULT_PLAN
    until = getattr(user, "plan_until", None)
    if plan != "free" and until is not None and until < datetime.utcnow():
        return "free"
    return plan


def _used_this_period(user):
    # usage_day holds the period key ("YYYY-MM"); reset when the month changes.
    if getattr(user, "usage_day", "") != _period():
        return 0
    return int(getattr(user, "usage_count", 0) or 0)


def snapshot(user):
    plan = effective_plan(user)
    lim = PLAN_LIMITS[plan]
    used = _used_this_period(user)
    return {
        "plan": plan,
        "plan_label": lim["label"],
        "limit": lim["monthly"],
        "used": used,
        "remaining": max(0, lim["monthly"] - used),
        "period": "month",
        "reminders_limit": lim["reminders"],
        "recordings_limit": lim["recordings"],
    }


def consume(user, n=1):
    """Count `n` commands against this month's allowance.

    Returns (ok, snapshot). When the month rolls over the counter resets. If the
    user is already at the limit nothing is charged and ok is False.
    """
    period = _period()
    if getattr(user, "usage_day", "") != period:
        user.usage_day = period
        user.usage_count = 0
    lim = PLAN_LIMITS[effective_plan(user)]
    if int(user.usage_count or 0) >= lim["monthly"]:
        return False, snapshot(user)
    user.usage_count = int(user.usage_count or 0) + n
    user.save()
    return True, snapshot(user)


def quota_response(snap):
    """The 402 returned to a client that's out of commands for the month."""
    return Response(json.dumps({
        "message": (f"You've used all {snap['limit']} of this month's commands on the "
                    f"{snap['plan_label']} plan. Upgrade for more, or try again next month."),
        "quota_exceeded": True,
        "usage": snap,
    }), status=402, mimetype="application/json")

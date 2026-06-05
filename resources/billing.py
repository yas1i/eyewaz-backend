"""
Membership: usage snapshot + command consumption, and a guarded dev endpoint
to switch plans for testing before real payments (Phase 2) are wired.
"""

import json
import os
from datetime import datetime, timedelta

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from database.models import Users
import usage


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


class UsageAPI(Resource):
    """GET a usage snapshot; POST consumes one command (used by the text reader,
    which has no heavy server endpoint of its own)."""

    @jwt_required()
    def get(self):
        user = Users.objects.get(email=get_jwt_identity())
        return _resp({"usage": usage.snapshot(user)}, 200)

    @jwt_required()
    def post(self):
        user = Users.objects.get(email=get_jwt_identity())
        ok, snap = usage.consume(user)
        if not ok:
            return usage.quota_response(snap)
        return _resp({"usage": snap}, 200)


class DevPlanAPI(Resource):
    """TEST ONLY. Set a user's plan without paying — guarded by the DEV_PLAN_KEY
    env var (disabled entirely when that var is unset). Remove once PayPal is live.
    """

    @jwt_required()
    def post(self):
        secret = os.getenv("DEV_PLAN_KEY")
        data = request.get_json(force=True, silent=True) or {}
        if not secret or data.get("key") != secret:
            return _resp({"message": "Not available."}, 403)
        plan = data.get("plan", "free")
        if plan not in usage.PLAN_LIMITS:
            return _resp({"message": "Unknown plan."}, 400)
        user = Users.objects.get(email=get_jwt_identity())
        user.plan = plan
        user.plan_until = None if plan == "free" else (datetime.utcnow() + timedelta(days=30))
        user.save()
        return _resp({"message": f"Plan set to {plan}.", "usage": usage.snapshot(user)}, 200)

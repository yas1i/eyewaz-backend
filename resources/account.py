"""Account details + listening preferences, and the Azure voice catalogue."""

import json

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from database.models import Users
from helpers import list_voices

_VOICES_CACHE = None  # the catalogue is large and static; fetch once.


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


class ProfileAPI(Resource):
    @jwt_required()
    def get(self):
        user = Users.objects.get(email=get_jwt_identity())
        return _resp({
            "name": user.name, "email": user.email, "phone": user.phone,
            "preferences": user.preferences(),
        }, 200)

    @jwt_required()
    def put(self):
        user = Users.objects.get(email=get_jwt_identity())
        data = request.get_json(force=True, silent=True) or {}
        if "name" in data:
            user.name = (data["name"] or "")[:30]
        if "phone" in data:
            user.phone = (data["phone"] or "")[:12]
        prefs = data.get("preferences") or {}
        if prefs.get("engine") in ("azure", "browser"):
            user.pref_engine = prefs["engine"]
        if prefs.get("language"):
            user.pref_language = prefs["language"][:10]
        if prefs.get("voice"):
            user.pref_voice = prefs["voice"]
        if "rate" in prefs:
            try:
                user.pref_rate = max(0.5, min(2.0, float(prefs["rate"])))
            except (TypeError, ValueError):
                pass
        user.save()
        return _resp({"message": "Your settings have been saved.",
                      "preferences": user.preferences()}, 200)


class VoicesAPI(Resource):
    @jwt_required()
    def get(self):
        global _VOICES_CACHE
        if _VOICES_CACHE is None:
            try:
                _VOICES_CACHE = list_voices()
            except Exception as e:
                return _resp({"message": f"Could not load voices: {e}"}, 502)
        return _resp({"voices": _VOICES_CACHE}, 200)

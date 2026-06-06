"""Account details + listening preferences, and the Azure voice catalogue."""

import json

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from database.models import Users, Docs, Folders, Images
from helpers import list_voices
import usage

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
            "todo_weekday": user.todo_weekday or "",
            "todo_weekend": user.todo_weekend or "",
            "usage": usage.snapshot(user),
        }, 200)

    @jwt_required()
    def put(self):
        user = Users.objects.get(email=get_jwt_identity())
        data = request.get_json(force=True, silent=True) or {}
        if "name" in data:
            user.name = (data["name"] or "")[:30]
        if "phone" in data:
            user.phone = (data["phone"] or "")[:12]
        if "todo_weekday" in data:
            user.todo_weekday = (data["todo_weekday"] or "")[:4000]
        if "todo_weekend" in data:
            user.todo_weekend = (data["todo_weekend"] or "")[:4000]
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

    @jwt_required()
    def delete(self):
        """Permanently delete the account and all its server-side data
        (required by the app stores)."""
        user = Users.objects(email=get_jwt_identity()).first()
        if not user:
            return _resp({"message": "Account already removed."}, 200)
        # Best-effort: stop any active subscription so they aren't billed again.
        try:
            import paypal_api
            if user.paypal_sub_id and paypal_api.configured():
                paypal_api.cancel_subscription(user.paypal_sub_id)
        except Exception:
            pass
        try:
            import stripe_api
            if user.stripe_sub_id and stripe_api.configured():
                stripe_api.cancel_subscription(user.stripe_sub_id)
        except Exception:
            pass
        # Remove the user's content, then the account.
        try:
            Docs.objects(user=user).delete()
            Folders.objects(user=user).delete()
            Images.objects(user=user).delete()
        except Exception:
            pass
        user.delete()
        return _resp({"message": "Your account and data have been deleted."}, 200)


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

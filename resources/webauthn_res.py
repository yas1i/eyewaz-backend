"""Passkey (Face ID / Touch ID) sign-in endpoints."""

import json

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token

from database.models import Users
import webauthn_api


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


class WebAuthnRegisterOptions(Resource):
    """Step 1 of enrolling a passkey — must be signed in first."""

    @jwt_required()
    def post(self):
        user = Users.objects.get(email=get_jwt_identity())
        existing = [c.get("id") for c in (user.webauthn_credentials or []) if c.get("id")]
        opts_json, challenge = webauthn_api.registration_options(
            request.host, user.email, str(user.id).encode(), existing)
        token = webauthn_api.sign_challenge(challenge, {"typ": "reg", "email": user.email})
        return _resp({"options": json.loads(opts_json), "token": token}, 200)


class WebAuthnRegisterVerify(Resource):
    """Step 2 — store the new passkey on the user."""

    @jwt_required()
    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        cred = data.get("credential")
        token = data.get("token")
        if not cred or not token:
            return _resp({"message": "Missing data."}, 400)
        try:
            claims = webauthn_api.read_token(token)
        except Exception:
            return _resp({"message": "Your enrolment timed out. Please try again."}, 400)
        identity = get_jwt_identity()
        if claims.get("typ") != "reg" or claims.get("email") != identity:
            return _resp({"message": "Invalid enrolment."}, 400)
        try:
            info = webauthn_api.verify_registration(json.dumps(cred), claims["c"], request.host, request)
        except Exception as e:
            return _resp({"message": f"Could not enable Face ID: {e}"}, 400)

        user = Users.objects.get(email=identity)
        creds = user.webauthn_credentials or []
        if not any(c.get("id") == info["id"] for c in creds):
            creds.append(info)
            user.webauthn_credentials = creds
            user.save()
        return _resp({"message": "Face ID sign-in is enabled on this device."}, 200)


class WebAuthnLoginOptions(Resource):
    """Step 1 of signing in with a passkey (no password). Email optional —
    omit it for usernameless Face ID where the device picks the passkey."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        allow = []
        if email:
            u = Users.objects(email=email).first()
            if u:
                allow = [c.get("id") for c in (u.webauthn_credentials or []) if c.get("id")]
        opts_json, challenge = webauthn_api.authentication_options(request.host, allow)
        token = webauthn_api.sign_challenge(challenge, {"typ": "auth"})
        return _resp({"options": json.loads(opts_json), "token": token}, 200)


class WebAuthnLoginVerify(Resource):
    """Step 2 — verify the assertion and issue a normal JWT."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        cred = data.get("credential")
        token = data.get("token")
        if not cred or not token:
            return _resp({"message": "Missing data."}, 400)
        try:
            claims = webauthn_api.read_token(token)
        except Exception:
            return _resp({"message": "Sign-in timed out. Please try again."}, 400)
        if claims.get("typ") != "auth":
            return _resp({"message": "Invalid sign-in."}, 400)

        cred_id = cred.get("id") or cred.get("rawId")
        user = Users.objects(__raw__={"webauthn_credentials.id": cred_id}).first()
        if not user:
            return _resp({"message": "This device isn't set up for Face ID sign-in yet."}, 401)
        stored = next((c for c in user.webauthn_credentials if c.get("id") == cred_id), None)
        if not stored:
            return _resp({"message": "Passkey not recognised."}, 401)

        try:
            new_count = webauthn_api.verify_authentication(
                json.dumps(cred), claims["c"], request.host, request,
                stored["public_key"], int(stored.get("sign_count", 0)))
        except Exception as e:
            return _resp({"message": f"Face ID sign-in failed: {e}"}, 401)

        stored["sign_count"] = new_count
        user.save()
        access = create_access_token(identity=user.email)
        return _resp({"token": access, "name": user.name, "email": user.email}, 200)

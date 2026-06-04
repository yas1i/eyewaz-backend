import json
import random
from datetime import datetime, timedelta

from flask import Response, request
from flask_restful import Resource
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token

from database.models import Users
from mailer import send_otp_email

OTP_TTL_MINUTES = 10


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _issue_otp(user, purpose):
    """Generate, store (hashed) and email a fresh 6-digit code."""
    code = f"{random.randint(0, 999999):06d}"
    user.otp_hash = generate_password_hash(code, method="pbkdf2:sha256")
    user.otp_expires = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    user.otp_purpose = purpose
    user.save()
    sent = send_otp_email(user.email, code)
    return sent


class UserSignUpAPI(Resource):
    """Create an account, then email a verification code (step 1 of 2)."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        for field in ("email", "name", "password", "confirmPassword"):
            if not data.get(field):
                return _resp({"message": f"Missing required field: {field}"}, 400)
        if data["password"] != data["confirmPassword"]:
            return _resp({"message": "Password and confirm password do not match."}, 400)
        if Users.objects(email=data["email"]).first():
            return _resp({"message": "An account with this email already exists."}, 409)

        user = Users(
            email=data["email"],
            name=data["name"],
            password=generate_password_hash(data["password"], method="pbkdf2:sha256"),
            phone=data.get("phone", ""),
            is_verified=False,
        ).save()
        _issue_otp(user, "signup")
        return _resp(
            {
                "requiresVerification": True,
                "email": user.email,
                "message": "We sent a 6-digit verification code to your email.",
            },
            200,
        )


class UserLoginAPI(Resource):
    """Check the password, then email a verification code (step 1 of 2)."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        try:
            user = Users.objects.get(email=data.get("email"))
        except Users.DoesNotExist:
            return _resp({"message": "Invalid credentials"}, 401)

        if not check_password_hash(user.password, data.get("password", "")):
            return _resp({"message": "Invalid credentials"}, 401)

        _issue_otp(user, "login")
        return _resp(
            {
                "requiresVerification": True,
                "email": user.email,
                "message": "We sent a verification code to your email.",
            },
            200,
        )


class VerifyOtpAPI(Resource):
    """Step 2 of 2: check the emailed code and issue a JWT."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        email = data.get("email")
        code = (data.get("code") or "").strip()
        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            return _resp({"message": "Account not found"}, 404)

        if not user.otp_hash or not user.otp_expires:
            return _resp({"message": "No verification in progress. Please sign in again."}, 400)
        if datetime.utcnow() > user.otp_expires:
            return _resp({"message": "That code has expired. Please request a new one."}, 400)
        if not check_password_hash(user.otp_hash, code):
            return _resp({"message": "Incorrect code. Please try again."}, 401)

        # Success — clear the one-time code and mark verified.
        user.is_verified = True
        user.otp_hash = None
        user.otp_expires = None
        user.otp_purpose = None
        user.save()

        access_token = create_access_token(identity=user.email)
        return _resp(
            {
                "userMeta": {"name": user.name, "email": user.email, "phone": user.phone},
                "isLoggedIn": True,
                "token": access_token,
            },
            200,
        )


class ResendOtpAPI(Resource):
    """Email a fresh verification code."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        try:
            user = Users.objects.get(email=data.get("email"))
        except Users.DoesNotExist:
            return _resp({"message": "Account not found"}, 404)
        _issue_otp(user, user.otp_purpose or "login")
        return _resp({"message": "A new code is on its way."}, 200)

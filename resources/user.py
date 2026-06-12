import json
import os
import random
from datetime import datetime, timedelta

from flask import Response, request
from flask_restful import Resource
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token

from database.models import Users
from mailer import send_otp_email

OTP_TTL_MINUTES = 10

# App-store review login: a single designated account can verify with a fixed
# code so Google/Apple reviewers (who can't read the OTP email) can sign in.
# Inactive unless BOTH env vars are set — keep them set only while in review.
REVIEW_EMAIL = os.getenv("REVIEW_EMAIL")
REVIEW_OTP = os.getenv("REVIEW_OTP")


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _verification_payload(email, dev_code):
    payload = {
        "requiresVerification": True,
        "email": email,
        "message": "We sent a 6-digit verification code to your email.",
    }
    if dev_code:  # SMTP not configured: surface the code so dev/testing works
        payload["dev_code"] = dev_code
        payload["message"] = "Email delivery isn't set up yet — use the code shown below."
    return payload


def _issue_otp(user, purpose):
    """Generate, store (hashed) and email a fresh 6-digit code.

    Returns the code only when email was NOT actually sent (dev mode, no SMTP),
    so the client can display it and the flow stays usable without email.
    """
    code = f"{random.randint(0, 999999):06d}"
    user.otp_hash = generate_password_hash(code, method="pbkdf2:sha256")
    user.otp_expires = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    user.otp_purpose = purpose
    user.save()
    sent = send_otp_email(user.email, code)
    return None if sent else code


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
        dev_code = _issue_otp(user, "signup")
        return _resp(_verification_payload(user.email, dev_code), 200)


class UserLoginAPI(Resource):
    """Check the password, then email a verification code (step 1 of 2)."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}

        # Hardcoded test/review logins — NO_OTP_USERS="a@b.com:pass1,c@d.com:pass2".
        # Exact email+password pairs sign in immediately, no email code: for
        # app-store reviewers and test devices. Unset the env var to disable.
        email_in = (data.get("email") or "").strip().lower()
        password_in = data.get("password") or ""
        for pair in (os.getenv("NO_OTP_USERS") or "").split(","):
            if ":" not in pair:
                continue
            em, pw = pair.split(":", 1)
            if email_in == em.strip().lower() and password_in == pw.strip():
                user = Users.objects(email=email_in).first()
                if not user:
                    user = Users(
                        email=email_in, name="Test User",
                        password=generate_password_hash(pw.strip(), method="pbkdf2:sha256"),
                        is_verified=True,
                    ).save()
                token = create_access_token(identity=user.email)
                return _resp({
                    "userMeta": {"name": user.name, "email": user.email, "phone": user.phone},
                    "isLoggedIn": True,
                    "token": token,
                }, 200)

        try:
            user = Users.objects.get(email=data.get("email"))
        except Users.DoesNotExist:
            return _resp({"message": "Invalid credentials"}, 401)

        if not check_password_hash(user.password, data.get("password", "")):
            return _resp({"message": "Invalid credentials"}, 401)

        dev_code = _issue_otp(user, "login")
        return _resp(_verification_payload(user.email, dev_code), 200)


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

        # Store-review bypass: the designated review account accepts a fixed code
        # (the reviewer can't see the emailed OTP). Env-gated; off in normal prod.
        if REVIEW_EMAIL and REVIEW_OTP and email == REVIEW_EMAIL and code == REVIEW_OTP:
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
        dev_code = _issue_otp(user, user.otp_purpose or "login")
        payload = {"message": "A new code is on its way."}
        if dev_code:
            payload["dev_code"] = dev_code
            payload["message"] = "Email delivery isn't set up yet — use the code shown below."
        return _resp(payload, 200)


class ForgotPasswordAPI(Resource):
    """Step 1 of password reset: email a code (doesn't reveal if email exists)."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        email = data.get("email")
        generic = "If that email has an account, we've sent a reset code."
        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            return _resp({"message": generic, "email": email}, 200)
        dev_code = _issue_otp(user, "reset")
        payload = {"message": generic, "email": email}
        if dev_code:
            payload["dev_code"] = dev_code
            payload["message"] = "Email delivery isn't set up yet — use the code shown below."
        return _resp(payload, 200)


class ResetPasswordAPI(Resource):
    """Step 2 of password reset: verify the code and set a new password."""

    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        email = data.get("email")
        code = (data.get("code") or "").strip()
        new_password = data.get("newPassword") or ""
        if len(new_password) < 8:
            return _resp({"message": "Your new password must be at least 8 characters."}, 400)
        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            return _resp({"message": "Account not found"}, 404)
        if not user.otp_hash or not user.otp_expires:
            return _resp({"message": "No reset in progress. Please request a code again."}, 400)
        if datetime.utcnow() > user.otp_expires:
            return _resp({"message": "That code has expired. Please request a new one."}, 400)
        if not check_password_hash(user.otp_hash, code):
            return _resp({"message": "Incorrect code. Please try again."}, 401)

        user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
        user.is_verified = True
        user.otp_hash = None
        user.otp_expires = None
        user.otp_purpose = None
        user.save()
        token = create_access_token(identity=user.email)
        return _resp(
            {
                "message": "Your password has been updated.",
                "token": token,
                "isLoggedIn": True,
                "userMeta": {"name": user.name, "email": user.email},
            },
            200,
        )

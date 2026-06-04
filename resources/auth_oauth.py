"""
Social sign-in (Google / Facebook / Apple) via OAuth2 Authorization Code flow.

Each provider activates automatically once its credentials are present in the
environment. Until then, the buttons still appear but redirect back with a
friendly "not configured" message.

Flow:
  GET /api/auth/<provider>/start     -> 302 to the provider's consent screen
  GET /api/auth/<provider>/callback  -> exchange code, find/create user,
                                        302 to /app#token=<jwt>
  GET /api/auth/providers            -> { google: bool, apple: bool, facebook: bool }
"""

import os
import secrets
from urllib.parse import urlencode

import requests
from flask import request, redirect
from flask_restful import Resource
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token

from database.models import Users

PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "id_env": "GOOGLE_CLIENT_ID",
        "secret_env": "GOOGLE_CLIENT_SECRET",
        "userinfo_auth": "bearer",
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,name,email",
        "scope": "email public_profile",
        "id_env": "FACEBOOK_APP_ID",
        "secret_env": "FACEBOOK_APP_SECRET",
        "userinfo_auth": "param",
    },
    # Apple uses a signed-JWT client secret and form_post callback — configure
    # APPLE_CLIENT_ID etc. to enable; treated as "not configured" until then.
    "apple": {
        "id_env": "APPLE_CLIENT_ID",
        "secret_env": "APPLE_CLIENT_SECRET",
        "configurable": False,
    },
}


def _base_url():
    return os.getenv("OAUTH_REDIRECT_BASE",
                     os.getenv("PUBLIC_BASE_URL", "http://localhost:4242")).rstrip("/")


def _app_redirect(fragment):
    return redirect(f"{_base_url()}/app#{fragment}")


def _is_configured(name):
    cfg = PROVIDERS.get(name)
    return bool(cfg and cfg.get("id_env") and os.getenv(cfg["id_env"])
                and cfg.get("auth_url"))


def _redirect_uri(provider):
    return f"{_base_url()}/api/auth/{provider}/callback"


def _find_or_create_user(email, name):
    user = Users.objects(email=email).first()
    if not user:
        user = Users(
            email=email,
            name=name or email.split("@")[0],
            # Social accounts have no usable password; store a random hash.
            password=generate_password_hash(secrets.token_urlsafe(24), method="pbkdf2:sha256"),
            is_verified=True,
        ).save()
    return user


class AuthProviders(Resource):
    def get(self):
        return {name: _is_configured(name) for name in PROVIDERS}


class OAuthStart(Resource):
    def get(self, provider):
        if not _is_configured(provider):
            return _app_redirect(f"auth_error={provider}_not_configured")
        cfg = PROVIDERS[provider]
        params = {
            "client_id": os.getenv(cfg["id_env"]),
            "redirect_uri": _redirect_uri(provider),
            "response_type": "code",
            "scope": cfg["scope"],
            "state": secrets.token_urlsafe(16),
        }
        return redirect(f"{cfg['auth_url']}?{urlencode(params)}")


class OAuthCallback(Resource):
    def get(self, provider):
        if not _is_configured(provider):
            return _app_redirect(f"auth_error={provider}_not_configured")
        cfg = PROVIDERS[provider]
        code = request.args.get("code")
        if not code:
            return _app_redirect("auth_error=cancelled")

        try:
            token_resp = requests.post(cfg["token_url"], data={
                "code": code,
                "client_id": os.getenv(cfg["id_env"]),
                "client_secret": os.getenv(cfg["secret_env"]),
                "redirect_uri": _redirect_uri(provider),
                "grant_type": "authorization_code",
            }, headers={"Accept": "application/json"}, timeout=20)
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return _app_redirect("auth_error=token_exchange_failed")

            if cfg["userinfo_auth"] == "bearer":
                info = requests.get(cfg["userinfo_url"],
                                    headers={"Authorization": f"Bearer {access_token}"}, timeout=20).json()
            else:  # param (Facebook)
                info = requests.get(cfg["userinfo_url"],
                                    params={"access_token": access_token}, timeout=20).json()

            email = info.get("email")
            if not email:
                return _app_redirect("auth_error=no_email")
            user = _find_or_create_user(email, info.get("name", ""))
            jwt = create_access_token(identity=user.email)
            return _app_redirect(f"token={jwt}")
        except Exception:
            return _app_redirect("auth_error=signin_failed")

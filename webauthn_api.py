"""
Passkey (Face ID / Touch ID / fingerprint) sign-in via WebAuthn.

The biometric never leaves the device — the authenticator holds a private key
and we store only the public key. Challenges are handed to the client inside a
short-lived signed token (stateless across gunicorn workers) and checked on the
way back.

Optional env:
  WEBAUTHN_RP_ID    relying-party id (the domain, e.g. eyewaz.com). Defaults to
                    the request host without port.
  WEBAUTHN_ORIGIN   expected origin (e.g. https://eyewaz.com). Defaults to the
                    request's host URL.
"""

import os
import time

import jwt
import webauthn
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)

RP_NAME = "EYEWAZ"
CHALLENGE_TTL = 300  # seconds


def rp_id(host):
    return os.getenv("WEBAUTHN_RP_ID") or (host or "localhost").split(":")[0]


def origin(req):
    return os.getenv("WEBAUTHN_ORIGIN") or req.host_url.rstrip("/")


def _secret():
    return os.getenv("JWT_SECRET_KEY") or "eyewaz-dev-secret"


def sign_challenge(challenge_bytes, extra=None):
    payload = {"c": bytes_to_base64url(challenge_bytes), "exp": int(time.time()) + CHALLENGE_TTL}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(), algorithm="HS256")


def read_token(token):
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def _descriptors(ids):
    return [PublicKeyCredentialDescriptor(id=base64url_to_bytes(i)) for i in ids]


def registration_options(host, user_email, user_id_bytes, existing_ids):
    opts = webauthn.generate_registration_options(
        rp_id=rp_id(host),
        rp_name=RP_NAME,
        user_name=user_email,
        user_id=user_id_bytes,
        user_display_name=user_email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=_descriptors(existing_ids),
    )
    return webauthn.options_to_json(opts), opts.challenge


def verify_registration(credential_json, expected_challenge_b64, host, req):
    v = webauthn.verify_registration_response(
        credential=credential_json,
        expected_challenge=base64url_to_bytes(expected_challenge_b64),
        expected_rp_id=rp_id(host),
        expected_origin=origin(req),
        require_user_verification=False,
    )
    return {
        "id": bytes_to_base64url(v.credential_id),
        "public_key": bytes_to_base64url(v.credential_public_key),
        "sign_count": v.sign_count,
    }


def authentication_options(host, allow_ids):
    opts = webauthn.generate_authentication_options(
        rp_id=rp_id(host),
        allow_credentials=_descriptors(allow_ids) or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    return webauthn.options_to_json(opts), opts.challenge


def verify_authentication(credential_json, expected_challenge_b64, host, req, public_key_b64, sign_count):
    v = webauthn.verify_authentication_response(
        credential=credential_json,
        expected_challenge=base64url_to_bytes(expected_challenge_b64),
        expected_rp_id=rp_id(host),
        expected_origin=origin(req),
        credential_public_key=base64url_to_bytes(public_key_b64),
        credential_current_sign_count=sign_count,
        require_user_verification=False,
    )
    return v.new_sign_count

"""
Thin PayPal REST helper for subscriptions (no PayPal SDK — just `requests`).

Card details never touch our app: the user approves on PayPal's hosted pages
via the JS SDK Smart Buttons; we only verify the resulting subscription and
listen to webhooks. Everything is gated on PAYPAL_CLIENT_ID / PAYPAL_SECRET
being set, so the app runs fine before payments are configured.

Env:
  PAYPAL_CLIENT_ID, PAYPAL_SECRET      REST app credentials
  PAYPAL_ENV            sandbox (default) | live
  PAYPAL_PLAN_MONTHLY  billing plan id for the Monthly plan
  PAYPAL_PLAN_SUPERMAX billing plan id for the Super Max plan
  PAYPAL_WEBHOOK_ID    id of the webhook (for signature verification)
  PAYPAL_CURRENCY      ISO currency (default GBP)
"""

import os
import requests

TIMEOUT = 25


def env():
    return "live" if os.getenv("PAYPAL_ENV", "sandbox").lower() == "live" else "sandbox"


def _base():
    return "https://api-m.paypal.com" if env() == "live" else "https://api-m.sandbox.paypal.com"


def currency():
    return os.getenv("PAYPAL_CURRENCY", "GBP")


def configured():
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_SECRET"))


def plans():
    return {"monthly": os.getenv("PAYPAL_PLAN_MONTHLY"), "supermax": os.getenv("PAYPAL_PLAN_SUPERMAX")}


def enabled():
    """Fully wired = creds + both plan ids present."""
    p = plans()
    return configured() and bool(p["monthly"] and p["supermax"])


def plan_for_id(plan_id):
    p = plans()
    if plan_id and plan_id == p["monthly"]:
        return "monthly"
    if plan_id and plan_id == p["supermax"]:
        return "supermax"
    return None


def _token():
    r = requests.post(
        _base() + "/v1/oauth2/token",
        auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_SECRET")),
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}


def get_subscription(sub_id):
    tok = _token()
    r = requests.get(_base() + f"/v1/billing/subscriptions/{sub_id}", headers=_h(tok), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def cancel_subscription(sub_id, reason="Cancelled by user"):
    tok = _token()
    requests.post(
        _base() + f"/v1/billing/subscriptions/{sub_id}/cancel",
        headers=_h(tok), json={"reason": reason[:127]}, timeout=TIMEOUT,
    )


def create_product_and_plans(prices, cur=None):
    """One-time setup: create a product + a monthly billing plan per tier.
    `prices` = {"monthly": "4.99", "supermax": "9.99"}. Returns the ids."""
    cur = cur or currency()
    tok = _token()
    h = _h(tok)
    pr = requests.post(_base() + "/v1/catalogs/products", headers=h, json={
        "name": "EYEWAZ Membership", "type": "SERVICE", "category": "SOFTWARE",
    }, timeout=TIMEOUT)
    pr.raise_for_status()
    product_id = pr.json()["id"]
    out = {"product_id": product_id}
    for tier, price in prices.items():
        body = {
            "product_id": product_id,
            "name": f"EYEWAZ {tier.title()}",
            "status": "ACTIVE",
            "billing_cycles": [{
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0,
                "pricing_scheme": {"fixed_price": {"value": str(price), "currency_code": cur}},
            }],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 2,
            },
        }
        rp = requests.post(_base() + "/v1/billing/plans", headers=h, json=body, timeout=TIMEOUT)
        rp.raise_for_status()
        out[tier] = rp.json()["id"]
    return out


def verify_webhook(headers, event):
    """Verify a webhook delivery with PayPal. Requires PAYPAL_WEBHOOK_ID."""
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        return False
    try:
        tok = _token()
        payload = {
            "transmission_id": headers.get("Paypal-Transmission-Id"),
            "transmission_time": headers.get("Paypal-Transmission-Time"),
            "cert_url": headers.get("Paypal-Cert-Url"),
            "auth_algo": headers.get("Paypal-Auth-Algo"),
            "transmission_sig": headers.get("Paypal-Transmission-Sig"),
            "webhook_id": webhook_id,
            "webhook_event": event,
        }
        r = requests.post(_base() + "/v1/notifications/verify-webhook-signature",
                          headers=_h(tok), json=payload, timeout=TIMEOUT)
        return r.ok and r.json().get("verification_status") == "SUCCESS"
    except Exception:
        return False

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
import paypal_api
import stripe_api


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


# A paid plan is granted ~33 days at a time; webhooks extend it on each renewal.
_PAID_DAYS = 33


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


# ----------------------------- PayPal subscriptions -------------------------- #

class PayPalConfigAPI(Resource):
    """Public-ish config the client needs to render PayPal buttons."""

    def get(self):
        return _resp({
            "enabled": paypal_api.enabled(),
            "client_id": os.getenv("PAYPAL_CLIENT_ID") if paypal_api.enabled() else None,
            "env": paypal_api.env(),
            "currency": paypal_api.currency(),
            "plans": paypal_api.plans() if paypal_api.enabled() else {},
        }, 200)


class PayPalActivateAPI(Resource):
    """Called from the Smart Button onApprove: verify the subscription with
    PayPal and switch the user onto the paid plan."""

    @jwt_required()
    def post(self):
        if not paypal_api.enabled():
            return _resp({"message": "Payments are not set up yet."}, 503)
        data = request.get_json(force=True, silent=True) or {}
        sub_id = (data.get("subscription_id") or "").strip()
        if not sub_id:
            return _resp({"message": "Missing subscription."}, 400)
        try:
            sub = paypal_api.get_subscription(sub_id)
        except Exception as e:
            return _resp({"message": f"Could not verify the subscription: {e}"}, 502)

        status = sub.get("status")
        if status not in ("ACTIVE", "APPROVED"):
            return _resp({"message": f"Subscription is not active yet ({status})."}, 400)

        plan = paypal_api.plan_for_id(sub.get("plan_id")) or data.get("plan")
        if plan not in ("monthly", "supermax"):
            return _resp({"message": "Unknown plan."}, 400)

        user = Users.objects.get(email=get_jwt_identity())
        user.plan = plan
        user.plan_until = datetime.utcnow() + timedelta(days=_PAID_DAYS)
        user.paypal_sub_id = sub_id
        user.save()
        return _resp({"message": f"You're now on the {plan} plan. Thank you!",
                      "usage": usage.snapshot(user)}, 200)


class PayPalCancelAPI(Resource):
    """Cancel the user's PayPal subscription (stays paid until the period ends)."""

    @jwt_required()
    def post(self):
        user = Users.objects.get(email=get_jwt_identity())
        if user.paypal_sub_id and paypal_api.configured():
            try:
                paypal_api.cancel_subscription(user.paypal_sub_id)
            except Exception:
                pass
        # Leave plan_until as-is so they keep access until it lapses; webhook
        # (CANCELLED/EXPIRED) will downgrade, and effective_plan() expires it anyway.
        return _resp({"message": "Your subscription will not renew.",
                      "usage": usage.snapshot(user)}, 200)


class PayPalSetupAPI(Resource):
    """TEST/setup helper: create the PayPal product + billing plans and return
    the ids to put in env. Guarded by DEV_PLAN_KEY."""

    @jwt_required()
    def post(self):
        secret = os.getenv("DEV_PLAN_KEY")
        data = request.get_json(force=True, silent=True) or {}
        if not secret or data.get("key") != secret:
            return _resp({"message": "Not available."}, 403)
        if not paypal_api.configured():
            return _resp({"message": "Set PAYPAL_CLIENT_ID and PAYPAL_SECRET first."}, 400)
        prices = data.get("prices") or {"monthly": "4.99", "supermax": "9.99"}
        try:
            ids = paypal_api.create_product_and_plans(prices, data.get("currency"))
        except Exception as e:
            return _resp({"message": f"PayPal setup failed: {e}"}, 502)
        return _resp({
            "message": "Plans created. Put these in your environment, then redeploy.",
            "PAYPAL_PLAN_MONTHLY": ids.get("monthly"),
            "PAYPAL_PLAN_SUPERMAX": ids.get("supermax"),
            "product_id": ids.get("product_id"),
        }, 200)


class PayPalWebhookAPI(Resource):
    """PayPal subscription lifecycle events → keep the user's plan in sync."""

    def post(self):
        event = request.get_json(force=True, silent=True) or {}
        if not paypal_api.verify_webhook(request.headers, event):
            return _resp({"message": "Invalid signature."}, 400)

        etype = event.get("event_type", "")
        resource = event.get("resource", {}) or {}
        # Subscription events carry the id directly; payment events reference it.
        sub_id = resource.get("id") or resource.get("billing_agreement_id")
        user = Users.objects(paypal_sub_id=sub_id).first() if sub_id else None
        if not user:
            return _resp({"message": "ok"}, 200)   # ack unknown/irrelevant events

        if etype in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RE-ACTIVATED",
                     "PAYMENT.SALE.COMPLETED", "PAYMENT.CAPTURE.COMPLETED"):
            plan = paypal_api.plan_for_id(resource.get("plan_id")) or user.plan
            if plan in ("monthly", "supermax"):
                user.plan = plan
            user.plan_until = datetime.utcnow() + timedelta(days=_PAID_DAYS)
            user.save()
        elif etype in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED",
                       "BILLING.SUBSCRIPTION.SUSPENDED"):
            user.plan = "free"
            user.plan_until = None
            user.paypal_sub_id = None
            user.save()
        return _resp({"message": "ok"}, 200)


# -------------------------- Stripe (card + Klarna) --------------------------- #

class StripeConfigAPI(Resource):
    def get(self):
        return _resp({"enabled": stripe_api.enabled()}, 200)


class StripeCheckoutAPI(Resource):
    """Create a hosted Checkout Session (card / Klarna) and return its URL."""

    @jwt_required()
    def post(self):
        if not stripe_api.enabled():
            return _resp({"message": "Card/Klarna payments are not set up yet."}, 503)
        data = request.get_json(force=True, silent=True) or {}
        plan = data.get("plan")
        if plan not in ("monthly", "supermax"):
            return _resp({"message": "Unknown plan."}, 400)
        user = Users.objects.get(email=get_jwt_identity())
        base = os.getenv("PUBLIC_BASE_URL") or request.host_url.rstrip("/")
        try:
            session = stripe_api.create_checkout(
                plan, user.email,
                success_url=base + "/app?checkout=success",
                cancel_url=base + "/app?checkout=cancel",
                customer_id=user.stripe_customer_id or None,
            )
        except Exception as e:
            return _resp({"message": f"Could not start checkout: {e}"}, 502)
        return _resp({"url": session.url}, 200)


class StripeWebhookAPI(Resource):
    """Stripe subscription lifecycle → keep the user's plan in sync."""

    def post(self):
        if not stripe_api.configured():
            return _resp({"message": "ok"}, 200)
        try:
            event = stripe_api.construct_event(request.get_data(), request.headers.get("Stripe-Signature"))
        except Exception:
            return _resp({"message": "Invalid signature."}, 400)

        etype = event.get("type", "")
        obj = (event.get("data") or {}).get("object", {}) or {}

        def _grant(user, plan, sub_id=None, cust=None):
            if plan in ("monthly", "supermax"):
                user.plan = plan
            user.plan_until = datetime.utcnow() + timedelta(days=_PAID_DAYS)
            if sub_id:
                user.stripe_sub_id = sub_id
            if cust:
                user.stripe_customer_id = cust
            user.save()

        if etype == "checkout.session.completed":
            email = ((obj.get("metadata") or {}).get("email")
                     or (obj.get("customer_details") or {}).get("email"))
            plan = (obj.get("metadata") or {}).get("plan")
            user = Users.objects(email=email).first() if email else None
            if user:
                _grant(user, plan, obj.get("subscription"), obj.get("customer"))

        elif etype in ("invoice.paid", "invoice.payment_succeeded"):
            cust = obj.get("customer")
            user = Users.objects(stripe_customer_id=cust).first() if cust else None
            if user:
                price_id = None
                try:
                    price_id = obj["lines"]["data"][0]["price"]["id"]
                except Exception:
                    pass
                _grant(user, stripe_api.price_to_plan(price_id) or user.plan,
                       obj.get("subscription"), cust)

        elif etype == "customer.subscription.deleted":
            sub_id = obj.get("id")
            user = Users.objects(stripe_sub_id=sub_id).first() if sub_id else None
            if user:
                user.plan = "free"; user.plan_until = None; user.stripe_sub_id = None
                user.save()

        return _resp({"message": "ok"}, 200)

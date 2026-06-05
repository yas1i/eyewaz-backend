"""
Stripe Checkout (subscriptions) — this is how EYEWAZ offers **Klarna and card**.

Stripe Checkout is a hosted page: the customer enters card/Klarna details on
Stripe, never on our app. We create a Checkout Session, redirect to it, and
listen to webhooks to keep the plan in sync.

Payment methods (card, Klarna, …) are controlled in the Stripe Dashboard
(Settings → Payment methods). Leave STRIPE_PMT_METHODS unset to let the
dashboard decide (recommended — enabling Klarna there makes it appear); or set
it to e.g. "card,klarna" to force a specific set.

Env:
  STRIPE_SECRET_KEY        sk_test_… / sk_live_…
  STRIPE_PRICE_MONTHLY     recurring price id for Monthly
  STRIPE_PRICE_SUPERMAX    recurring price id for Super Max
  STRIPE_WEBHOOK_SECRET    whsec_… (for webhook verification)
  STRIPE_PMT_METHODS       optional comma list, e.g. "card,klarna"
"""

import os


def configured():
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def prices():
    return {"monthly": os.getenv("STRIPE_PRICE_MONTHLY"), "supermax": os.getenv("STRIPE_PRICE_SUPERMAX")}


def enabled():
    p = prices()
    return configured() and bool(p["monthly"] and p["supermax"])


def _methods():
    raw = os.getenv("STRIPE_PMT_METHODS", "").strip()
    return [m.strip() for m in raw.split(",") if m.strip()] if raw else None


def _stripe():
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    return stripe


def price_to_plan(price_id):
    p = prices()
    if price_id and price_id == p["monthly"]:
        return "monthly"
    if price_id and price_id == p["supermax"]:
        return "supermax"
    return None


def create_checkout(plan, email, success_url, cancel_url, customer_id=None):
    stripe = _stripe()
    kwargs = dict(
        mode="subscription",
        line_items=[{"price": prices().get(plan), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"plan": plan, "email": email or ""},
        subscription_data={"metadata": {"plan": plan, "email": email or ""}},
        allow_promotion_codes=True,
    )
    methods = _methods()
    if methods:
        kwargs["payment_method_types"] = methods   # else dashboard decides
    if customer_id:
        kwargs["customer"] = customer_id
    elif email:
        kwargs["customer_email"] = email
    return stripe.checkout.Session.create(**kwargs)


def cancel_subscription(sub_id):
    try:
        _stripe().Subscription.modify(sub_id, cancel_at_period_end=True)
    except Exception:
        pass


def construct_event(payload, sig_header):
    """Verify a webhook payload. Raises on bad signature."""
    return _stripe().Webhook.construct_event(payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET"))

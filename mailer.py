"""
Email sending for 2-step verification codes.

Order of preference:
  1. SendGrid HTTP API (SENDGRID_API_KEY) — works on PaaS hosts that block SMTP.
  2. SMTP (SMTP_* env) — legacy; blocked on many free hosts.
  3. Dev fallback — log the message so the OTP flow stays testable with no setup.
"""

import os
import re
import smtplib
import ssl
from email.message import EmailMessage

import requests


def _from_address():
    raw = os.getenv("SENDGRID_FROM") or os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or ""
    m = re.search(r"<([^>]+)>", raw)
    return (m.group(1) if m else raw).strip()


def _send_via_sendgrid(to, subject, body):
    """Send via SendGrid's HTTP API (HTTPS — not blocked by PaaS)."""
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": _from_address()},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        },
        timeout=12,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"SendGrid {resp.status_code}: {resp.text[:200]}")
    return True


def smtp_configured():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def send_email(to, subject, body):
    """Send an email. Returns True if actually sent, False if dev-logged."""
    if os.getenv("SENDGRID_API_KEY"):
        return _send_via_sendgrid(to, subject, body)

    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"\n[DEV-EMAIL — no email provider configured]\n  To: {to}\n  Subject: {subject}\n  {body}\n", flush=True)
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)

    context = ssl.create_default_context()
    # A timeout is essential: some hosts (e.g. Render's free tier) block outbound
    # SMTP, and without a timeout the request would hang forever.
    timeout = int(os.getenv("SMTP_TIMEOUT", "12"))
    if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
    return True


def send_otp_email(to, code):
    subject = "Your EYEWAZ verification code"
    body = (
        f"Your EYEWAZ verification code is: {code}\n\n"
        "It expires in 10 minutes.\n"
        "If you didn't request this, you can safely ignore this email."
    )
    try:
        return send_email(to, subject, body)
    except Exception as e:
        # Never let a mail problem break sign-up: fall back to the dev code path.
        print(f"\n[EMAIL FAILED — falling back to on-screen code]\n  {e}\n  Code for {to}: {code}\n", flush=True)
        return False

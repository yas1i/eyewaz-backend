"""
Email sending for 2-step verification codes.

Configured via SMTP_* env vars. If SMTP is not configured, falls back to logging
the message to the console so the OTP flow is still testable in development.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage


def smtp_configured():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def send_email(to, subject, body):
    """Send an email. Returns True if actually sent, False if dev-logged."""
    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"\n[DEV-EMAIL — SMTP not configured]\n  To: {to}\n  Subject: {subject}\n  {body}\n", flush=True)
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
    if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as server:
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

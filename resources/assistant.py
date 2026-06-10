"""
EYEWAZ conversational assistant (optional, admin-enabled).

A blind or low-vision user speaks to the app; the browser turns that speech
into text and posts it here. We send the message — with the user's name and
saved to-do lists — to a hosted AI model and return a short, spoken-friendly
reply that the client reads aloud (browser TTS or Azure Urdu voice).

Off by default. An owner enables it from the admin toggle (AppSettings
.assistant_enabled). The AI provider/model and API key are read from the
environment, so the feature is fully configurable and ships disabled.
"""

import json
import os

from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from database.models import Users, AppSettings

# Lazily-created singleton so a missing SDK / key never crashes import or boot.
_CLIENT = None
_CLIENT_ERROR = None

# Provider + model are env-configurable; the feature is off unless an admin
# enables it and a key is set. Defaults can be overridden without code changes.
MODEL = os.getenv("ASSISTANT_MODEL", "claude-opus-4-8")


def _is_enabled():
    """Owner toggle (off by default). Stored in AppSettings, set via admin."""
    try:
        s = AppSettings.objects(key="singleton").first()
        return bool(s and s.assistant_enabled)
    except Exception:
        return False
MAX_TOKENS = 1024
MAX_TURNS = 12          # cap client-supplied history so the prompt stays bounded
MAX_MSG_CHARS = 4000    # cap a single user utterance

# Stable persona. Kept first and byte-identical across every request so the
# prompt-cache prefix is reused (cache_control below). Nothing user-specific
# goes in here — that lives in the message turns so the cache stays shared.
SYSTEM_PROMPT = (
    "You are Eyewaz, a warm, patient voice companion for people who are blind "
    "or have low vision. Your replies are read aloud by a screen reader, so you "
    "must write for the ear, not the eye.\n"
    "\n"
    "How to speak:\n"
    "- Keep replies short: usually one to three sentences. Get to the point.\n"
    "- Use plain, spoken language. No markdown, no bullet characters, no "
    "asterisks, no emoji, no headings, no code blocks, and no URLs unless the "
    "person asks for one.\n"
    "- When you must list things, say them as a natural sentence: 'First, ... "
    "Next, ... and finally, ...'.\n"
    "- Spell out anything that is confusing when heard. Say times and dates in "
    "full words, for example 'half past nine in the morning'.\n"
    "- Be encouraging and calm. Never rush the person or assume they can see "
    "the screen.\n"
    "\n"
    "What you help with:\n"
    "- Reading and talking through the person's to-do list for today.\n"
    "- Planning their day, reminders, and gentle encouragement.\n"
    "- Answering everyday questions and keeping friendly company.\n"
    "- Explaining how to use Eyewaz: it can photograph and read text aloud, "
    "read documents and web pages, translate, and speak in many languages "
    "including Urdu.\n"
    "\n"
    "If you are unsure what the person wants, ask one short, friendly question. "
    "Reply only with what you want spoken aloud, nothing else."
)


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _get_client():
    """Build the Anthropic client once. Returns (client, error_message)."""
    global _CLIENT, _CLIENT_ERROR
    if _CLIENT is not None or _CLIENT_ERROR is not None:
        return _CLIENT, _CLIENT_ERROR
    if not os.getenv("ANTHROPIC_API_KEY"):
        _CLIENT_ERROR = "The assistant is not configured yet. Please add an Anthropic API key."
        return None, _CLIENT_ERROR
    try:
        import anthropic
        _CLIENT = anthropic.Anthropic()
    except Exception as e:  # SDK not installed, bad key format, etc.
        _CLIENT_ERROR = f"The assistant could not start: {e}"
    return _CLIENT, _CLIENT_ERROR


def _context_block(user):
    """A short, per-user context note prepended to the conversation.

    Kept out of the system prompt (which is cached and shared) and phrased as
    context, not commands.
    """
    name = (user.name or "").strip() if user else ""
    weekday = (user.todo_weekday or "").strip() if user else ""
    weekend = (user.todo_weekend or "").strip() if user else ""

    lines = ["Here is what you know about the person you are talking to."]
    lines.append(f"Their name is {name}." if name else "You do not know their name yet.")
    if weekday:
        lines.append(f"Their usual weekday to-do list is:\n{weekday}")
    if weekend:
        lines.append(f"Their usual weekend to-do list is:\n{weekend}")
    if not weekday and not weekend:
        lines.append("They have not saved a to-do list yet. You can offer to "
                     "help them think of one.")
    lines.append("Use this only when it is relevant to what they ask.")
    return "\n".join(lines)


def _clean_history(raw):
    """Sanitize client-supplied prior turns into valid alternating messages."""
    history = []
    if isinstance(raw, list):
        for item in raw[-MAX_TURNS:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                history.append({"role": role, "content": content.strip()[:MAX_MSG_CHARS]})
    return history


class AssistantConfigAPI(Resource):
    """Report whether the assistant is on (so the UI shows/hides it) and let an
    owner flip it. Off by default; toggling needs DEV_PLAN_KEY."""

    def get(self):
        return _resp({"enabled": _is_enabled(),
                      "configured": bool(os.getenv("ANTHROPIC_API_KEY"))}, 200)

    def post(self):
        secret = os.getenv("DEV_PLAN_KEY")
        data = request.get_json(force=True, silent=True) or {}
        if not secret or data.get("key") != secret:
            return _resp({"message": "Owner key required."}, 401)
        s = AppSettings.objects(key="singleton").first() or AppSettings(key="singleton")
        s.assistant_enabled = bool(data.get("enabled"))
        s.save()
        return _resp({"enabled": s.assistant_enabled}, 200)


class AssistantAPI(Resource):
    @jwt_required()
    def post(self):
        if not _is_enabled():
            return _resp({"message": "The assistant is turned off."}, 403)
        data = request.get_json(force=True, silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return _resp({"message": "I didn't catch that. Could you say it again?"}, 400)
        message = message[:MAX_MSG_CHARS]

        client, err = _get_client()
        if err:
            return _resp({"message": err}, 503)

        user = Users.objects(email=get_jwt_identity()).first()

        import usage
        if user:
            ok, snap = usage.consume(user)
            if not ok:
                return usage.quota_response(snap)

        # Build the conversation: per-user context, then prior turns, then the
        # new message. The context goes in the first user turn so the cached
        # system prefix stays identical for every user.
        history = _clean_history(data.get("history"))
        messages = []
        if not history:
            messages.append({"role": "user", "content": _context_block(user)})
            messages.append({"role": "assistant",
                             "content": "Got it. I'm here and ready to help."})
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            import anthropic
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "disabled"},          # snappy conversational replies
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # reuse the shared prefix
                }],
                messages=messages,
            )
        except anthropic.APIStatusError as e:
            return _resp({"message": "Sorry, I'm having trouble thinking right now. "
                                     "Please try again in a moment.",
                          "detail": getattr(e, "message", str(e))}, 502)
        except Exception as e:
            return _resp({"message": "Sorry, I couldn't reach the assistant. "
                                     "Please try again in a moment.",
                          "detail": str(e)}, 502)

        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        if not reply:
            reply = "I'm not sure how to answer that. Could you ask me another way?"
        return _resp({"reply": reply}, 200)

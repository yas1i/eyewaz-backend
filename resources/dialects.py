"""
Pakistani dialect / regional-voice picker.

Phase 1: a curated catalogue of Pakistani regional varieties. At request time we
check which entries actually have a working Azure voice and mark the rest
"coming soon" (they fall back to standard Urdu until a cloned dialect voice is
added in Phase 2 — at which point we just fill in `clone_voice` for that entry).

Picking a dialect sets the user's translation language + TTS voice, so the whole
read-aloud pipeline (photo, document, web, My Day, assistant) speaks it.
"""

import json
import os
from datetime import datetime

from flask import Response, request
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from helpers import list_voices
from database.models import DialectVoice
import elevenlabs_api

FALLBACK_VOICE = "ur-PK-UzmaNeural"
FALLBACK_LOCALE = "ur-PK"

# Biggest regional varieties first. `voices` are candidate Azure short-names;
# only the ones the live catalogue actually has are surfaced. Empty / missing =>
# "coming soon" (Phase 2 cloned voice bank).
CATALOG = [
    {"id": "urdu",    "label": "Standard Urdu",        "region": "National",            "locale": "ur-PK", "voices": ["ur-PK-UzmaNeural", "ur-PK-AsadNeural"]},
    {"id": "urdu-selfhost", "label": "Urdu — open-source (free)", "region": "Self-hosted", "locale": "ur-PK", "voices": [], "selfhost": True},
    {"id": "punjabi", "label": "Punjabi · Urdu",       "region": "Punjab",              "locale": "pa-IN", "voices": ["pa-IN-VaaniNeural", "pa-IN-OjasNeural", "pa-IN-GurpreetNeural"]},
    {"id": "pashto",  "label": "Pashto · Urdu",        "region": "Khyber Pakhtunkhwa",  "locale": "ps-AF", "voices": ["ps-AF-LatifaNeural", "ps-AF-GulNawazNeural"]},
    {"id": "sindhi",  "label": "Sindhi · Karachi Urdu","region": "Sindh",               "locale": "ur-PK", "voices": []},
    {"id": "saraiki", "label": "Saraiki",              "region": "South Punjab",        "locale": "ur-PK", "voices": []},
    {"id": "hindko",  "label": "Hindko",               "region": "Hazara",              "locale": "ur-PK", "voices": []},
    {"id": "balochi", "label": "Balochi",              "region": "Balochistan",         "locale": "ur-PK", "voices": []},
    {"id": "brahui",  "label": "Brahui",               "region": "Balochistan",         "locale": "ur-PK", "voices": []},
]

_VOICE_CACHE = None


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


class DialectsAPI(Resource):
    @jwt_required()
    def get(self):
        global _VOICE_CACHE
        if _VOICE_CACHE is None:
            try:
                _VOICE_CACHE = list_voices()
            except Exception:
                _VOICE_CACHE = []
        by_name = {v.get("shortName"): v for v in (_VOICE_CACHE or [])}
        cloned = {dv.dialect_id: dv for dv in DialectVoice.objects()}

        out = []
        selfhost_on = bool(os.getenv("SELF_HOST_TTS_URL"))
        for d in CATALOG:
            if d.get("selfhost"):
                live = selfhost_on
                out.append({
                    "id": d["id"], "label": d["label"], "region": d["region"],
                    "locale": "ur-PK", "status": "live" if live else "soon",
                    "voices": ([{"shortName": "sh:urdu", "gender": "", "engine": "selfhost",
                                 "name": "Open-source Urdu"}] if live else []),
                    "cloned": False, "tier": "free",
                    "fallback_voice": FALLBACK_VOICE, "fallback_locale": FALLBACK_LOCALE,
                })
                continue
            dv = cloned.get(d["id"])
            present = [by_name[n] for n in d["voices"] if n in by_name]
            if dv and dv.voice_id:
                # A cloned dialect voice exists — it wins. Voice value is "el:<id>";
                # text is still translated to Urdu, the clone speaks it in-dialect.
                voices = [{"shortName": "el:" + dv.voice_id, "gender": "", "engine": "clone",
                           "name": (dv.speaker or d["label"]) + " (cloned)"}]
                status, locale = "live", FALLBACK_LOCALE
            elif present:
                voices = [{"shortName": v.get("shortName"), "gender": v.get("gender", ""),
                           "engine": "azure", "name": v.get("displayName", v.get("shortName"))} for v in present]
                status, locale = "live", d["locale"]
            else:
                voices, status, locale = [], "soon", FALLBACK_LOCALE
            is_clone = bool(dv and dv.voice_id)
            out.append({
                "id": d["id"], "label": d["label"], "region": d["region"],
                "locale": locale, "status": status, "voices": voices,
                "cloned": is_clone,
                # Azure + open-source self-host voices are free; cloned dialect
                # voices are part of the premium package.
                "tier": "premium" if is_clone else "free",
                "fallback_voice": FALLBACK_VOICE, "fallback_locale": FALLBACK_LOCALE,
            })
        return _resp({"dialects": out}, 200)


_CATALOG_IDS = {d["id"]: d for d in CATALOG}


class DialectCloneAPI(Resource):
    """Owner tool: turn a consenting native-speaker recording into a cloned
    dialect voice. Guarded by DEV_PLAN_KEY; needs ELEVENLABS_API_KEY."""

    @jwt_required()
    def post(self):
        secret = os.getenv("DEV_PLAN_KEY")
        key = request.form.get("key")
        if not secret or key != secret:
            return _resp({"message": "Not available."}, 403)
        if not elevenlabs_api.configured():
            return _resp({"message": "Set ELEVENLABS_API_KEY first."}, 400)
        dialect_id = request.form.get("dialect_id", "")
        if dialect_id not in _CATALOG_IDS:
            return _resp({"message": "Unknown dialect."}, 400)
        if request.form.get("consent") != "true":
            return _resp({"message": "Speaker consent is required."}, 400)
        if "audio" not in request.files:
            return _resp({"message": "Please attach an audio sample."}, 400)
        f = request.files["audio"]
        speaker = (request.form.get("speaker") or "").strip()[:80]
        label = _CATALOG_IDS[dialect_id]["label"]
        try:
            voice_id = elevenlabs_api.add_voice(
                f"EYEWAZ {label}", f.read(), filename=f.filename or "sample.webm",
                content_type=f.mimetype or "application/octet-stream",
                description=f"EYEWAZ {label} dialect voice; speaker: {speaker}; consented.",
            )
        except Exception as e:
            return _resp({"message": f"Cloning failed: {e}"}, 502)
        DialectVoice(dialect_id=dialect_id, engine="elevenlabs", voice_id=voice_id,
                     speaker=speaker, consent_at=datetime.utcnow()).save()
        return _resp({"message": f"{label} voice created and is now live.",
                      "dialect_id": dialect_id, "voice_id": voice_id}, 200)

    @jwt_required()
    def delete(self):
        secret = os.getenv("DEV_PLAN_KEY")
        data = request.get_json(force=True, silent=True) or {}
        if not secret or data.get("key") != secret:
            return _resp({"message": "Not available."}, 403)
        dialect_id = data.get("dialect_id")
        dv = DialectVoice.objects(dialect_id=dialect_id).first()
        if dv:
            if dv.voice_id:
                elevenlabs_api.delete_voice(dv.voice_id)
            dv.delete()
        return _resp({"message": "Removed."}, 200)

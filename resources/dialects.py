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

from flask import Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from helpers import list_voices

FALLBACK_VOICE = "ur-PK-UzmaNeural"
FALLBACK_LOCALE = "ur-PK"

# Biggest regional varieties first. `voices` are candidate Azure short-names;
# only the ones the live catalogue actually has are surfaced. Empty / missing =>
# "coming soon" (Phase 2 cloned voice bank).
CATALOG = [
    {"id": "urdu",    "label": "Standard Urdu",        "region": "National",            "locale": "ur-PK", "voices": ["ur-PK-UzmaNeural", "ur-PK-AsadNeural"]},
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

        out = []
        for d in CATALOG:
            present = [by_name[n] for n in d["voices"] if n in by_name]
            out.append({
                "id": d["id"],
                "label": d["label"],
                "region": d["region"],
                "locale": d["locale"] if present else FALLBACK_LOCALE,
                "status": "live" if present else "soon",
                "voices": [{
                    "shortName": v.get("shortName"),
                    "gender": v.get("gender", ""),
                    "name": v.get("displayName", v.get("shortName")),
                } for v in present],
                "fallback_voice": FALLBACK_VOICE,
                "fallback_locale": FALLBACK_LOCALE,
            })
        return _resp({"dialects": out}, 200)

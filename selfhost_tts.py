"""
Client for the self-hosted EYEWAZ Urdu TTS engine (tts-service/), which serves
our own trained Piper voices.

Dormant until SELF_HOST_TTS_URL is set, so the app runs fine without it and
falls back to Azure. Voice ids are stored in user preferences as "sh:<id>",
e.g. "sh:urdu-female"; everything after "sh:" is what the engine understands.

Env:
  SELF_HOST_TTS_URL   base URL of the tts-service (e.g. https://tts.eyewaz.com)
  SELF_HOST_TTS_KEY   value sent as X-API-Key (must match TTS_API_KEY there)
"""

import io
import os
import time

import requests

_VOICES_CACHE = None      # (fetched_at, [voice dicts]) — successes only
_VOICES_TTL = 300


def configured():
    return bool(os.getenv("SELF_HOST_TTS_URL"))


def _base():
    return os.getenv("SELF_HOST_TTS_URL", "").rstrip("/")


def _headers():
    key = os.getenv("SELF_HOST_TTS_KEY")
    return {"X-API-Key": key} if key else {}


def voices():
    """The engine's real voice list, cached for 5 minutes.

    Only successful responses are cached, so one blip does not blank the
    listener's voice picker for the next five minutes.
    """
    global _VOICES_CACHE
    if not configured():
        return []
    if _VOICES_CACHE and (time.time() - _VOICES_CACHE[0]) < _VOICES_TTL:
        return _VOICES_CACHE[1]
    try:
        r = requests.get(_base() + "/voices", headers=_headers(), timeout=10)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return _VOICES_CACHE[1] if _VOICES_CACHE else []
    except Exception:
        return _VOICES_CACHE[1] if _VOICES_CACHE else []
    _VOICES_CACHE = (time.time(), data)
    return data


def default_voice():
    """App-facing id of the voice to use for Urdu when the user has no
    preference, e.g. "sh:eyewaz-urdu-female". None if the engine has nothing."""
    available = voices()
    if not available:
        return None
    for v in available:
        if v.get("gender") == "female" and v.get("language") == "ur":
            return "sh:" + v["id"]
    for v in available:
        if v.get("language") == "ur":
            return "sh:" + v["id"]
    return "sh:" + available[0]["id"]


def _chunks(text, size=900):
    words, cur, out = text.split(" "), "", []
    for w in words:
        if len(cur) + len(w) + 1 > size:
            if cur:
                out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        out.append(cur)
    return out or [text]


def synth(text, speed=1.0, voice=None):
    """Return one WAV for arbitrary-length text (chunked + concatenated).

    ``voice`` is the engine-side id, i.e. the preference value with "sh:"
    already stripped. Passing None lets the engine pick its own default.
    """
    import numpy as np
    import soundfile as sf

    arrs, sr = [], None
    for piece in _chunks((text or "").strip()):
        if not piece.strip():
            continue
        payload = {"text": piece, "speed": speed}
        if voice:
            payload["voice"] = voice
        r = requests.post(_base() + "/tts", json=payload,
                          headers=_headers(), timeout=120)
        r.raise_for_status()
        data, this_sr = sf.read(io.BytesIO(r.content), dtype="float32")
        sr = this_sr
        arrs.append(data)
    if not arrs:
        return b""
    out = np.concatenate(arrs)
    buf = io.BytesIO()
    sf.write(buf, out, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()

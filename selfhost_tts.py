"""
Client for the self-hosted open-source Urdu TTS service (tts-service/).
Dormant until SELF_HOST_TTS_URL is set, so the app runs fine without it.

Env:
  SELF_HOST_TTS_URL   base URL of the tts-service (e.g. https://tts.eyewaz.com)
"""

import io
import os

import requests


def configured():
    return bool(os.getenv("SELF_HOST_TTS_URL"))


def _base():
    return os.getenv("SELF_HOST_TTS_URL", "").rstrip("/")


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


def synth(text, speed=1.0):
    """Return one WAV for arbitrary-length text (chunked + concatenated)."""
    import numpy as np
    import soundfile as sf

    arrs, sr = [], None
    for piece in _chunks((text or "").strip()):
        if not piece.strip():
            continue
        r = requests.post(_base() + "/tts", json={"text": piece, "speed": speed}, timeout=120)
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

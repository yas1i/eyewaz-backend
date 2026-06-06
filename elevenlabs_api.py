"""
Voice cloning via ElevenLabs — used to build the EYEWAZ dialect voice bank from
consenting native-speaker recordings. Dormant until ELEVENLABS_API_KEY is set.

Env:
  ELEVENLABS_API_KEY     your ElevenLabs API key
  ELEVENLABS_MODEL       optional tts model (default eleven_multilingual_v2)
"""

import os
import requests

BASE = "https://api.elevenlabs.io/v1"
TIMEOUT = 90


def configured():
    return bool(os.getenv("ELEVENLABS_API_KEY"))


def _key():
    return os.getenv("ELEVENLABS_API_KEY")


def model():
    return os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")


def add_voice(name, audio_bytes, filename="sample.webm", content_type="application/octet-stream", description=""):
    """Create an instant voice clone from one sample. Returns voice_id."""
    r = requests.post(
        BASE + "/voices/add",
        headers={"xi-api-key": _key()},
        data={"name": (name or "EYEWAZ voice")[:80],
              "description": (description or "EYEWAZ dialect voice (speaker consented)")[:480]},
        files={"files": (filename, audio_bytes, content_type)},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("voice_id")


def tts(voice_id, text, settings=None):
    """Synthesise text in a cloned voice. Returns MP3 bytes."""
    body = {"text": text, "model_id": model()}
    if settings:
        body["voice_settings"] = settings
    r = requests.post(
        BASE + f"/text-to-speech/{voice_id}",
        headers={"xi-api-key": _key(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json=body,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.content


def delete_voice(voice_id):
    try:
        requests.delete(BASE + f"/voices/{voice_id}", headers={"xi-api-key": _key()}, timeout=30)
    except Exception:
        pass

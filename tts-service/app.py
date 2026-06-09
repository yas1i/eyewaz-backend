"""
EYEWAZ self-hosted Urdu TTS microservice (open-source, no per-character fees).

Engine: Meta MMS-TTS (`facebook/mms-tts-urd`) — an open, multilingual VITS model
with a real Urdu voice. Runs on CPU (fine for short screen-reader utterances) or
GPU (faster). This one HTTP service is the shared backbone for:
  - the EYEWAZ app (set SELF_HOST_TTS_URL and route "selfhost" voices here),
  - an Android system TTS-engine app (stream /tts to TalkBack),
  - an NVDA add-on / Chrome read-aloud extension.

Dialect voices: clone native speakers with OpenVoice/XTTS on top of this base and
serve them as additional /tts?voice=... ids (see README, Phase 2).

Endpoints:
  GET  /healthz            -> {"ok": true, "model": ...}
  POST /tts  {text, ...}   -> audio/wav   (also GET /tts?text=... for quick tests)
"""

import io
import os

import numpy as np
import soundfile as sf
import torch
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from transformers import VitsModel, AutoTokenizer


def require_key(x_api_key: str | None = Header(default=None)):
    """If TTS_API_KEY is set, require a matching X-API-Key header on /tts."""
    key = os.getenv("TTS_API_KEY")
    if key and x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid API key")

MODEL_ID = os.getenv("TTS_MODEL", "facebook/mms-tts-urd-script_arabic")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "1200"))

app = FastAPI(title="EYEWAZ Urdu TTS")
_model = None
_tok = None
_uro = None


def _load():
    global _model, _tok
    if _model is None:
        _tok = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = VitsModel.from_pretrained(MODEL_ID).to(DEVICE).eval()
    return _model, _tok


def _romanize(text: str) -> str:
    """MMS-TTS for non-Latin scripts (Urdu, etc.) needs romanized input."""
    global _uro
    if _uro is None:
        import uroman as ur
        _uro = ur.Uroman()
    return _uro.romanize_string(text)


class TTSIn(BaseModel):
    text: str
    speed: float | None = None   # 0.5–2.0 (MMS exposes a length/speaking-rate scale)


def _synth(text: str, speed: float | None) -> bytes:
    model, tok = _load()
    text = (text or "").strip()[:MAX_CHARS]
    if not text:
        return b""
    # Normalize Urdu (numbers→words, symbols, punctuation) — big intelligibility win.
    if os.getenv("TTS_NORMALIZE", "1") != "0" and "urd" in MODEL_ID:
        import normalize_urdu
        text = normalize_urdu.normalize(text)
    if getattr(tok, "is_uroman", False):
        text = _romanize(text)
    inputs = tok(text, return_tensors="pt").to(DEVICE)
    if speed:
        try:
            model.speaking_rate = max(0.5, min(2.0, float(speed)))
        except Exception:
            pass
    with torch.no_grad():
        wav = model(**inputs).waveform[0].detach().cpu().float().numpy()
    wav = np.clip(wav, -1.0, 1.0)
    buf = io.BytesIO()
    sf.write(buf, wav, model.config.sampling_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": MODEL_ID, "device": DEVICE}


@app.post("/tts", dependencies=[Depends(require_key)])
def tts_post(body: TTSIn):
    audio = _synth(body.text, body.speed)
    if not audio:
        return JSONResponse({"message": "No text."}, status_code=400)
    return Response(content=audio, media_type="audio/wav")


@app.get("/tts", dependencies=[Depends(require_key)])
def tts_get(text: str = "", speed: float | None = None):
    audio = _synth(text, speed)
    if not audio:
        return JSONResponse({"message": "No text."}, status_code=400)
    return Response(content=audio, media_type="audio/wav")

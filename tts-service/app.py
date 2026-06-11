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
# Our own trained voice: set PIPER_MODEL to a Piper .onnx path to use it instead
# of MMS (cheap CPU inference, our licence). Swapping models = one env var.
PIPER_MODEL = os.getenv("PIPER_MODEL")
# Interim Azure-quality Urdu: set SPEECH_KEY + REGION to route /tts through Azure
# Neural TTS until the trained Piper voice is ready. Priority: Piper > Azure > MMS.
AZURE_KEY = os.getenv("SPEECH_KEY")
AZURE_REGION = os.getenv("SPEECH_REGION") or os.getenv("REGION")
AZURE_VOICE = os.getenv("AZURE_VOICE", "ur-PK-UzmaNeural")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "1200"))

app = FastAPI(title="EYEWAZ Urdu TTS")
_model = None
_tok = None
_uro = None
_piper = None


def _piper_voice():
    global _piper
    if _piper is None:
        from piper import PiperVoice
        cfg = PIPER_MODEL + ".json"
        _piper = PiperVoice.load(PIPER_MODEL, config_path=cfg if os.path.exists(cfg) else None)
    return _piper


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
    text = (text or "").strip()[:MAX_CHARS]
    if not text:
        return b""
    norm = os.getenv("TTS_NORMALIZE", "1") != "0"
    # Our trained Piper voice (if configured).
    if PIPER_MODEL:
        return _synth_piper(_maybe_normalize(text, norm), speed)
    # Interim: Azure Neural Urdu (good quality) if keys are set. Azure handles its
    # own text/number normalization, so we pass the raw text.
    if AZURE_KEY and AZURE_REGION:
        return _synth_azure(text, speed)
    # Otherwise MMS.
    model, tok = _load()
    text = _maybe_normalize(text, norm and "urd" in MODEL_ID)
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


def _maybe_normalize(text: str, enabled: bool) -> str:
    """Urdu number/text normalization — optional and never fatal if the module
    isn't present in the image."""
    if not enabled:
        return text
    try:
        import normalize_urdu
        return normalize_urdu.normalize(text)
    except Exception:
        return text


def _synth_piper(text: str, speed: float | None) -> bytes:
    """piper-tts 1.3.x (OHF-Voice) API: synthesize() yields AudioChunk objects;
    we assemble them into a WAV ourselves."""
    import wave
    voice = _piper_voice()
    length_scale = (1.0 / float(speed)) if (speed and float(speed) != 1.0) else 1.0
    try:
        from piper import SynthesisConfig
        chunks = list(voice.synthesize(text, syn_config=SynthesisConfig(length_scale=length_scale)))
    except TypeError:
        chunks = list(voice.synthesize(text))   # tolerate signature changes
    if not chunks:
        return b""
    rate = getattr(chunks[0], "sample_rate", 22050)
    audio = b"".join(getattr(c, "audio_int16_bytes", b"") for c in chunks)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(audio)
    return buf.getvalue()


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def _synth_azure(text: str, speed: float | None) -> bytes:
    """Azure Neural TTS via REST (returns 22.05 kHz mono 16-bit WAV)."""
    import urllib.request
    body = _xml_escape(text)
    if speed and float(speed) != 1.0:
        rate = f"{int((float(speed) - 1.0) * 100):+d}%"
        body = f"<prosody rate='{rate}'>{body}</prosody>"
    ssml = (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ur-PK'>"
            f"<voice name='{AZURE_VOICE}'>{body}</voice></speak>")
    url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    req = urllib.request.Request(url, data=ssml.encode("utf-8"), headers={
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
        "User-Agent": "eyewaz-tts",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


@app.get("/healthz")
def healthz():
    engine = "piper" if PIPER_MODEL else ("azure" if (AZURE_KEY and AZURE_REGION) else "mms")
    model = PIPER_MODEL or (AZURE_VOICE if engine == "azure" else MODEL_ID)
    return {"ok": True, "engine": engine, "model": model, "device": DEVICE}


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

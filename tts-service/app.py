"""
EYEWAZ self-hosted Urdu TTS microservice (open-source, no per-character fees).

Engine: our own Piper voices, trained on the EYEWAZ voice bank. The service
serves a FOLDER of voices (`VOICES_DIR`), so male and female, and later other
languages, are one deployment rather than one container per voice. This one HTTP
service is the shared backbone for:
  - the EYEWAZ app (set SELF_HOST_TTS_URL and route "sh:" voices here),
  - an Android system TTS-engine app (stream /tts to TalkBack),
  - an NVDA add-on / Chrome read-aloud extension.

Fallbacks, in priority order, are kept so a box without the voice files still
speaks: Piper (ours) > Azure Neural (if SPEECH_KEY set) > Meta MMS. torch and
transformers are imported lazily, so a Piper-only image does not need them.

Endpoints:
  GET  /healthz            -> {"ok": true, "engine": ..., "voices": [...]}
  GET  /voices             -> [{"id","name","gender","language","sample_rate"}]
  POST /tts  {text, voice, speed}   -> audio/wav
  GET  /tts?text=...&voice=...      -> audio/wav   (quick tests)
"""

import io
import os
import wave

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import voices as registry


def require_key(x_api_key: str | None = Header(default=None)):
    """If TTS_API_KEY is set, require a matching X-API-Key header on /tts."""
    key = os.getenv("TTS_API_KEY")
    if key and x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid API key")


_HERE = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.getenv("VOICES_DIR", os.path.join(_HERE, "voices"))
MODEL_ID = os.getenv("TTS_MODEL", "facebook/mms-tts-urd-script_arabic")
# Legacy single-voice env, kept so an old deployment keeps working after upgrade.
PIPER_MODEL = os.getenv("PIPER_MODEL")
AZURE_KEY = os.getenv("SPEECH_KEY")
AZURE_REGION = os.getenv("SPEECH_REGION") or os.getenv("REGION")
AZURE_VOICE = os.getenv("AZURE_VOICE", "ur-PK-UzmaNeural")
MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "1200"))

VOICES = registry.discover(VOICES_DIR)
if PIPER_MODEL and os.path.exists(PIPER_MODEL):
    VOICES.update(registry.discover(os.path.dirname(os.path.abspath(PIPER_MODEL))))
ALIASES = registry.alias_map(VOICES)
DEFAULT_VOICE = registry.default_id(VOICES)

app = FastAPI(title="EYEWAZ Urdu TTS")
_model = None
_tok = None
_uro = None
_loaded = {}      # canonical id -> PiperVoice, loaded on first use and kept


def _piper_voice(voice_id):
    """Load and cache one Piper voice. Each costs roughly 200 MB resident."""
    if voice_id not in _loaded:
        from piper import PiperVoice
        info = VOICES[voice_id]
        _loaded[voice_id] = PiperVoice.load(info["model"], config_path=info["config"])
    return _loaded[voice_id]


def _load():
    global _model, _tok
    if _model is None:
        import torch
        from transformers import VitsModel, AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = VitsModel.from_pretrained(MODEL_ID).to(_device()).eval()
    return _model, _tok


def _device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _romanize(text: str) -> str:
    """MMS-TTS for non-Latin scripts (Urdu, etc.) needs romanized input."""
    global _uro
    if _uro is None:
        import uroman as ur
        _uro = ur.Uroman()
    return _uro.romanize_string(text)


class TTSIn(BaseModel):
    text: str
    voice: str | None = None     # "eyewaz-urdu-female", "female", "sh:urdu-male", ...
    speed: float | None = None   # 0.5-2.0


def _resolve(voice):
    """Canonical voice id, or raise 400 listing what we do have.

    An unknown id is never silently swapped for another voice: a listener who
    picked male must not be handed female without being told.
    """
    if not VOICES:
        return None
    if not voice:
        return DEFAULT_VOICE
    hit = registry.resolve(voice, VOICES, ALIASES)
    if not hit:
        raise HTTPException(status_code=400,
                            detail=f"Unknown voice '{voice}'. Available: {', '.join(VOICES)}")
    return hit


def _synth(text: str, speed: float | None, voice: str | None = None) -> bytes:
    text = (text or "").strip()[:MAX_CHARS]
    if not text:
        return b""
    norm = os.getenv("TTS_NORMALIZE", "1") != "0"
    voice_id = _resolve(voice)
    # Our own trained voices.
    if voice_id:
        return _synth_piper(_maybe_normalize(text, norm), speed, voice_id)
    # Interim: Azure Neural Urdu if keys are set. Azure handles its own text and
    # number normalization, so we pass the raw text.
    if AZURE_KEY and AZURE_REGION:
        return _synth_azure(text, speed)
    # Otherwise MMS.
    import numpy as np
    import soundfile as sf
    import torch
    model, tok = _load()
    text = _maybe_normalize(text, norm and "urd" in MODEL_ID)
    if getattr(tok, "is_uroman", False):
        text = _romanize(text)
    inputs = tok(text, return_tensors="pt").to(_device())
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


def _synth_piper(text: str, speed: float | None, voice_id: str) -> bytes:
    """piper-tts (OHF-Voice) API: synthesize() yields AudioChunk objects;
    we assemble them into a WAV ourselves."""
    voice = _piper_voice(voice_id)
    length_scale = (1.0 / float(speed)) if (speed and float(speed) != 1.0) else 1.0
    try:
        from piper import SynthesisConfig
        chunks = list(voice.synthesize(text, syn_config=SynthesisConfig(length_scale=length_scale)))
    except TypeError:
        chunks = list(voice.synthesize(text))   # tolerate signature changes
    if not chunks:
        return b""
    rate = getattr(chunks[0], "sample_rate", VOICES[voice_id]["sample_rate"])
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
    """Azure Neural TTS via REST (returns 24 kHz mono 16-bit WAV)."""
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


def _public(info):
    return {k: info[k] for k in ("id", "name", "gender", "language", "sample_rate")}


@app.get("/healthz")
def healthz():
    engine = "piper" if VOICES else ("azure" if (AZURE_KEY and AZURE_REGION) else "mms")
    return {"ok": True, "engine": engine, "voices": list(VOICES),
            "default": DEFAULT_VOICE, "voices_dir": VOICES_DIR, "device": _device()}


@app.get("/voices")
def list_voices():
    return [_public(v) for v in VOICES.values()]


@app.post("/tts", dependencies=[Depends(require_key)])
def tts_post(body: TTSIn):
    audio = _synth(body.text, body.speed, body.voice)
    if not audio:
        return JSONResponse({"message": "No text."}, status_code=400)
    return Response(content=audio, media_type="audio/wav")


@app.get("/tts", dependencies=[Depends(require_key)])
def tts_get(text: str = "", voice: str | None = None, speed: float | None = None):
    audio = _synth(text, speed, voice)
    if not audio:
        return JSONResponse({"message": "No text."}, status_code=400)
    return Response(content=audio, media_type="audio/wav")

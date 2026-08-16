#!/usr/bin/env python3
"""
EYEWAZ local Piper voice server — instant, offline, zero-cost Urdu speech.

Runs your trained Piper .onnx on the user's own machine and exposes the SAME
HTTP contract as the cloud tts-service, so every EYEWAZ client works unchanged
by just pointing its URL at this local server:

  - NVDA add-on:  set TTS_URL = http://127.0.0.1:59125  in eyewaz.json
  - Chrome ext.:  set TTS service URL = http://127.0.0.1:59125  in the popup
  - SAPI engine:  POSTs to http://127.0.0.1:59125/tts  (see windows-sapi/)

Endpoints (identical to tts-service):
  GET  /healthz                 -> {"ok": true, "engine": "piper", ...}
  GET  /voices                  -> [{"id","name","gender","language","sample_rate"}]
  POST /tts {text,voice,speed}  -> audio/wav   (also GET /tts?text=... for tests)

Pure standard library + piper-tts — no FastAPI/torch. Tiny and fast on CPU.

Usage:
  pip install piper-tts
  python piper_server.py --voices-dir ./voices --port 59125
  python piper_server.py --model /path/eyewaz-urdu-female.onnx   # single voice
  # (or set VOICES_DIR / PIPER_MODEL and just run `python piper_server.py`)
"""

import argparse
import io
import json
import os
import subprocess
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import voices as registry

_loaded = {}      # canonical id -> PiperVoice
_args = None
VOICES = {}
ALIASES = {}
DEFAULT_VOICE = None


def _load_voice(voice_id):
    if voice_id not in _loaded:
        from piper import PiperVoice  # lazy: only needed when we synthesize
        info = VOICES[voice_id]
        _loaded[voice_id] = PiperVoice.load(info["model"], config_path=info["config"])
    return _loaded[voice_id]


def _normalize(text):
    """Optional Urdu normalization, shared with the cloud service if available."""
    if not _args.normalize:
        return text
    try:
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(here, "..", "tts-service"))
        import normalize_urdu
        return normalize_urdu.normalize(text)
    except Exception:
        return text


def _synth_via_exe(text, speed, info):
    """Synthesize by shelling out to the bundled rhasspy piper.exe.

    Used where piper1-gpl's compiled espeakbridge is unavailable (Windows on
    ARM, or any machine without the pip wheel), and to share ONE runtime with
    the NVDA add-on. piper.exe streams raw 16-bit PCM to stdout; we wrap it in a
    WAV container so the HTTP reply is identical to the piper1-gpl path.
    """
    exe = _args.piper_exe
    length_scale = (1.0 / float(speed)) if speed else 1.0
    args = [exe, "--model", info["model"], "--output_raw",
            "--length_scale", "%.3f" % length_scale]
    if info.get("config"):
        args += ["--config", info["config"]]
    creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    proc = subprocess.run(
        args, input=text.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(exe)),  # so piper finds its DLLs + espeak-ng-data
        creationflags=creationflags,
    )
    pcm = proc.stdout or b""
    if not pcm:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[-300:]
                           or "piper.exe produced no audio")
    rate = int(info.get("sample_rate", 22050))
    buf = io.BytesIO()
    wf = wave.open(buf, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(rate)
    wf.writeframes(pcm)
    wf.close()
    return buf.getvalue()


def synth(text, speed, voice_id=None):
    text = (text or "").strip()
    if not text:
        return b""
    text = _normalize(text)
    vid = voice_id or DEFAULT_VOICE
    if _args.piper_exe:
        return _synth_via_exe(text, speed, VOICES[vid])
    voice = _load_voice(vid)

    # piper-tts (piper1-gpl) synthesize() returns an iterable of AudioChunk,
    # it no longer writes into a wave.Wave_write directly (older rhasspy API did).
    from piper.config import SynthesisConfig
    syn_config = SynthesisConfig(length_scale=(1.0 / float(speed))) if speed else None

    buf = io.BytesIO()
    wf = None
    for chunk in voice.synthesize(text, syn_config):
        if wf is None:
            wf = wave.open(buf, "wb")
            wf.setnchannels(chunk.sample_channels)
            wf.setsampwidth(chunk.sample_width)
            wf.setframerate(chunk.sample_rate)
        wf.writeframes(chunk.audio_int16_bytes)
    if wf is not None:
        wf.close()
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _auth_ok(self):
        if not _args.api_key:
            return True
        return self.headers.get("X-API-Key") == _args.api_key

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()
        self.wfile.write(body)

    def _audio(self, text, speed, voice=None):
        if not self._auth_ok():
            return self._send(401, {"message": "Invalid API key"})
        voice_id = DEFAULT_VOICE
        if voice:
            voice_id = registry.resolve(voice, VOICES, ALIASES)
            # Never silently swap one voice for another: say what we have.
            if not voice_id:
                return self._send(400, {"message": f"Unknown voice '{voice}'. "
                                                   f"Available: {', '.join(VOICES)}"})
        try:
            wav = synth(text, speed, voice_id)
        except Exception as e:
            return self._send(500, {"message": f"Synthesis failed: {e}"})
        if not wav:
            return self._send(400, {"message": "No text."})
        self._send(200, wav, ctype="audio/wav")

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/healthz":
            return self._send(200, {"ok": True, "engine": "piper",
                                    "voices": list(VOICES), "default": DEFAULT_VOICE})
        if u.path == "/voices":
            return self._send(200, [{k: v[k] for k in
                                     ("id", "name", "gender", "language", "sample_rate")}
                                    for v in VOICES.values()])
        if u.path == "/tts":
            q = parse_qs(u.query)
            text = (q.get("text", [""])[0])
            speed = float(q.get("speed", [0])[0] or 0) or None
            return self._audio(text, speed, (q.get("voice", [""])[0]) or None)
        self._send(404, {"message": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/tts":
            return self._send(404, {"message": "Not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            data = {}
        self._audio(data.get("text", ""), data.get("speed"), data.get("voice"))

    def log_message(self, *a):
        pass   # quiet


def main():
    global _args, VOICES, ALIASES, DEFAULT_VOICE
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="EYEWAZ local Piper TTS server")
    p.add_argument("--voices-dir", default=os.getenv("VOICES_DIR", os.path.join(here, "voices")),
                   help="folder of <id>.onnx voices (or set VOICES_DIR)")
    p.add_argument("--model", default=os.getenv("PIPER_MODEL"),
                   help="single .onnx voice, instead of a folder (or set PIPER_MODEL)")
    p.add_argument("--config", default=os.getenv("PIPER_CONFIG"),
                   help="path to the .onnx.json (defaults to <model>.json)")
    p.add_argument("--piper-exe", default=os.getenv("PIPER_EXE"),
                   help="shell out to this rhasspy piper.exe instead of the "
                        "piper1-gpl Python bindings (needed on Windows/ARM, "
                        "shares one runtime with the NVDA add-on)")
    p.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "59125")))
    p.add_argument("--api-key", default=os.getenv("TTS_API_KEY", ""),
                   help="optional X-API-Key to require (usually unset for localhost)")
    p.add_argument("--normalize", action="store_true",
                   help="apply Urdu number/text normalization (needs tts-service/)")
    _args = p.parse_args()

    if _args.model:
        if not os.path.exists(_args.model):
            p.error(f"model not found: {_args.model}")
        VOICES = registry.discover(os.path.dirname(os.path.abspath(_args.model)))
    else:
        VOICES = registry.discover(_args.voices_dir)
    if not VOICES:
        p.error(f"no voices found in {_args.voices_dir}: each needs <id>.onnx + <id>.onnx.json")
    ALIASES = registry.alias_map(VOICES)
    DEFAULT_VOICE = registry.default_id(VOICES)

    server = ThreadingHTTPServer((_args.host, _args.port), Handler)
    print(f"EYEWAZ local Piper voices on http://{_args.host}:{_args.port}")
    for vid in VOICES:
        print(f"  {vid}{'  (default)' if vid == DEFAULT_VOICE else ''}")
    print("Point NVDA/Chrome/SAPI at that URL. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

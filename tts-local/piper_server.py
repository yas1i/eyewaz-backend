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
  GET  /healthz           -> {"ok": true, "engine": "piper", ...}
  POST /tts {text,speed}  -> audio/wav     (also GET /tts?text=... for quick tests)

Pure standard library + piper-tts — no FastAPI/torch. Tiny and fast on CPU.

Usage:
  pip install piper-tts
  python piper_server.py --model /path/eyewaz-urdu-female.onnx --port 59125
  # (or set PIPER_MODEL=/path/...onnx and just run `python piper_server.py`)
"""

import argparse
import io
import json
import os
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

_voice = None
_args = None


def _load_voice():
    global _voice
    if _voice is None:
        from piper import PiperVoice  # lazy: only needed when we synthesize
        cfg = _args.config or (_args.model + ".json")
        _voice = PiperVoice.load(_args.model, config_path=cfg if os.path.exists(cfg) else None)
    return _voice


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


def synth(text, speed):
    text = (text or "").strip()
    if not text:
        return b""
    text = _normalize(text)
    voice = _load_voice()
    length_scale = (1.0 / float(speed)) if speed else None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        try:
            if length_scale:
                voice.synthesize(text, wf, length_scale=length_scale)
            else:
                voice.synthesize(text, wf)
        except TypeError:
            voice.synthesize(text, wf)   # older piper API without length_scale
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

    def _audio(self, text, speed):
        if not self._auth_ok():
            return self._send(401, {"message": "Invalid API key"})
        try:
            wav = synth(text, speed)
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
            return self._send(200, {"ok": True, "engine": "piper", "model": _args.model})
        if u.path == "/tts":
            q = parse_qs(u.query)
            text = (q.get("text", [""])[0])
            speed = float(q.get("speed", [0])[0] or 0) or None
            return self._audio(text, speed)
        self._send(404, {"message": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/tts":
            return self._send(404, {"message": "Not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            data = {}
        self._audio(data.get("text", ""), data.get("speed"))

    def log_message(self, *a):
        pass   # quiet


def main():
    global _args
    p = argparse.ArgumentParser(description="EYEWAZ local Piper TTS server")
    p.add_argument("--model", default=os.getenv("PIPER_MODEL"),
                   help="path to the Piper .onnx voice (or set PIPER_MODEL)")
    p.add_argument("--config", default=os.getenv("PIPER_CONFIG"),
                   help="path to the .onnx.json (defaults to <model>.json)")
    p.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "59125")))
    p.add_argument("--api-key", default=os.getenv("TTS_API_KEY", ""),
                   help="optional X-API-Key to require (usually unset for localhost)")
    p.add_argument("--normalize", action="store_true",
                   help="apply Urdu number/text normalization (needs tts-service/)")
    _args = p.parse_args()
    if not _args.model:
        p.error("no model: pass --model /path/voice.onnx or set PIPER_MODEL")
    if not os.path.exists(_args.model):
        p.error(f"model not found: {_args.model}")
    server = ThreadingHTTPServer((_args.host, _args.port), Handler)
    print(f"EYEWAZ local Piper voice on http://{_args.host}:{_args.port}  "
          f"(model: {os.path.basename(_args.model)})")
    print("Point NVDA/Chrome/SAPI at that URL. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

"""
Read a web page aloud: fetch a URL server-side (the browser can't, due to CORS),
extract the readable English text, and return it for the client to speak.
"""

import ipaddress
import json
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import request, Response
from flask_restful import Resource
from flask_jwt_extended import jwt_required

import storage
from flask_jwt_extended import get_jwt_identity
from database.models import Users
from helpers import translate, synthesize

SPEAK_MAX_CHARS = 6000  # cap Azure synthesis so long pages stay responsive

MAX_BYTES = 3_000_000   # don't download more than ~3 MB of HTML
MAX_CHARS = 20_000      # cap extracted text so TTS stays manageable


def _json(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _host_is_safe(host):
    """Block loopback/private/link-local/reserved targets (basic SSRF guard)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def _extract(html, fallback_title):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer",
                     "nav", "aside", "form", "svg"]):
        tag.decompose()
    title = fallback_title
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    # Prefer the main article region if the page marks one up.
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(main.get_text(separator=" ").split())
    return title, text[:MAX_CHARS]


class ReadUrlAPI(Resource):
    @jwt_required()
    def post(self):
        import usage
        user = Users.objects(email=get_jwt_identity()).first()
        if user:
            ok, snap = usage.consume(user)
            if not ok:
                return usage.quota_response(snap)

        data = request.get_json(force=True, silent=True) or {}
        url = (data.get("url") or "").strip()
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return _json({"message": "Please enter a valid web address starting with http:// or https://"}, 400)
        if not _host_is_safe(parsed.hostname):
            return _json({"message": "That address can’t be read for security reasons."}, 400)

        try:
            resp = requests.get(
                url, timeout=15, allow_redirects=True,
                headers={"User-Agent": "EyewazReader/1.0 (+accessibility reader)"},
            )
        except requests.RequestException as e:
            return _json({"message": f"Could not open the page: {e}"}, 502)

        # Re-check the final host in case a redirect pointed somewhere internal.
        final_host = urlparse(resp.url).hostname
        if final_host and not _host_is_safe(final_host):
            return _json({"message": "That address can’t be read for security reasons."}, 400)

        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            return _json({"message": "That link is not a readable web page."}, 415)

        html = resp.content[:MAX_BYTES].decode(resp.encoding or "utf-8", errors="ignore")
        title, text = _extract(html, parsed.hostname)

        if not text:
            return _json({"message": "No readable text was found on that page."}, 422)

        return _json({"title": title, "text": text, "url": resp.url}, 200)


def _split_for_translate(text, size=4500):
    """Split into <=size-char pieces on word boundaries (Azure caps request size)."""
    words = text.split(" ")
    pieces, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > size:
            if cur:
                pieces.append(cur)
            cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        pieces.append(cur)
    return pieces


class TranslateTextAPI(Resource):
    """Translate arbitrary text (e.g. an extracted web page) to Urdu."""

    @jwt_required()
    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()
        to = data.get("to", "ur-PK")
        if not text:
            return _json({"message": "There is no text to translate."}, 400)
        try:
            translated = " ".join(
                translate(piece, "en", to) for piece in _split_for_translate(text)
            )
        except Exception as e:
            return _json({"message": f"Translation failed: {e}"}, 502)
        return _json({"translated": translated, "to": to}, 200)


class SpeakAPI(Resource):
    """Synthesize text to speech with Azure (high-quality Urdu voices) and
    return an audio URL. Used where the browser has no matching voice (Urdu)."""

    @jwt_required()
    def post(self):
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return _json({"message": "There is no text to read."}, 400)

        user = Users.objects(email=get_jwt_identity()).first()
        prefs = user.preferences() if user else {}

        # Resolve the voice: explicit request > legacy female/male > saved pref.
        legacy = {"female": "ur-PK-UzmaNeural", "male": "ur-PK-AsadNeural"}
        voice = data.get("voiceName") or legacy.get(data.get("voice")) \
            or prefs.get("voice", "ur-PK-UzmaNeural")
        rate = data.get("rate", prefs.get("rate", 1.0))

        capped = text[:SPEAK_MAX_CHARS]
        # Self-hosted open-source Urdu voice ("sh:...") → our own TTS service.
        if isinstance(voice, str) and voice.startswith("sh:"):
            import selfhost_tts
            if selfhost_tts.configured():
                try:
                    audio = selfhost_tts.synth(capped, rate)
                    stored = storage.save_file(audio, "speech.wav")
                    return _json({"audio_url": stored.url,
                                  "truncated": len(text) > SPEAK_MAX_CHARS, "voice": voice}, 200)
                except Exception as e:
                    return _json({"message": f"Could not generate audio: {e}"}, 502)
            voice = "ur-PK-UzmaNeural"   # graceful fallback if engine not configured

        # Cloned dialect voices are stored as "el:<voice_id>" → synthesize via
        # ElevenLabs; everything else uses Azure.
        if isinstance(voice, str) and voice.startswith("el:"):
            import elevenlabs_api
            if not elevenlabs_api.configured():
                voice = "ur-PK-UzmaNeural"   # graceful fallback if key absent
            else:
                try:
                    audio = b""
                    for piece in _split_for_translate(capped, 2200):
                        audio += elevenlabs_api.tts(voice[3:], piece)
                    stored = storage.save_file(audio, "speech.mp3")
                    return _json({"audio_url": stored.url,
                                  "truncated": len(text) > SPEAK_MAX_CHARS, "voice": voice}, 200)
                except Exception as e:
                    return _json({"message": f"Could not generate audio: {e}"}, 502)

        try:
            audio = b""
            for piece in _split_for_translate(capped, 2500):
                audio += synthesize(piece, voice, rate).audio_data
        except Exception as e:
            return _json({"message": f"Could not generate audio: {e}"}, 502)

        stored = storage.save_file(audio, "speech.mp3")
        return _json({"audio_url": stored.url, "truncated": len(text) > SPEAK_MAX_CHARS,
                      "voice": voice}, 200)

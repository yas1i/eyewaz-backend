# EYEWAZ self-hosted Urdu TTS engine

An open-source, self-hostable Urdu text-to-speech HTTP service. It's the shared
voice backbone for EYEWAZ **and** for screen-reader access (the real unlock for
blind Urdu users — see "Why" below).

Engine: **Meta MMS-TTS `facebook/mms-tts-urd`** (open, VITS, real Urdu voice).
No per-character fees. Runs on CPU (ok for short utterances) or GPU (faster).

## Run it
```bash
cd tts-service
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements.txt
uvicorn app:app --port 8090
# test:
curl "http://localhost:8090/tts?text=السلام%20علیکم" --output hello.wav
```
Or Docker:
```bash
docker build -t eyewaz-tts .
docker run -p 8090:8090 eyewaz-tts
```
Deploy on any box with ~2–4 GB RAM (CPU) or a small GPU. First request loads the
model (a few seconds); after that it's fast. Put it behind HTTPS.

## API
- `GET /healthz` → `{ok, model, device}`
- `POST /tts` `{ "text": "...", "speed": 1.0 }` → **audio/wav**
- `GET /tts?text=...&speed=1.0` → audio/wav (quick test)

## Why this matters (how blind people access the app)
Blind users navigate via their **OS screen reader** (Android TalkBack, iOS
VoiceOver, Windows NVDA/JAWS), which speaks through the **system TTS engine**.
Android/iOS ship poor or no Pakistani-Urdu voices — so the whole phone is hard to
use in Urdu, not just EYEWAZ. This service feeds a high-quality Urdu voice to:

| Surface | How it uses this service |
|---|---|
| **EYEWAZ app** | Set `SELF_HOST_TTS_URL` on the backend and route "selfhost" voices to `POST /tts` (alternative to Azure). |
| **Android TTS-engine app** (biggest win) | A native `TextToSpeechService` that streams `/tts` audio. User selects "EYEWAZ Urdu" in Settings → TTS output → **TalkBack and every app** now speak Urdu. |
| **Windows NVDA add-on** | A synth driver that calls `/tts`; NVDA/JAWS read Urdu system-wide. |
| **Chrome read-aloud extension** | Reads selected/page text via `/tts`. |
| **iOS** | ❌ Apple does not allow replacing VoiceOver's voice — limited to Apple's Urdu voice. |

## Dialects (Phase 2)
MMS gives standard Urdu. For regional dialects, clone consenting native speakers
(see `docs/voice-bank/`) with **OpenVoice** or **XTTS** *on top of* this base, and
serve each as another voice id (`/tts?voice=<dialect>`). The voice-bank admin tool
already collects the recordings.

## Wiring EYEWAZ to this engine (optional)
Add `SELF_HOST_TTS_URL=https://your-tts-host` to the EYEWAZ backend env, then in
`resources/web.py` `SpeakAPI`, route a chosen "self-hosted" voice to this service
(POST text → save the returned wav). Keeps Azure as default; self-host as a free,
private, offline-capable alternative.

## Limits / notes
- MMS Urdu is good, not perfect; quality improves with dialect cloning.
- CPU latency grows with text length — screen readers send short chunks, which is
  ideal. For app-length documents, prefer GPU or chunk the text.
- Licence: MMS is released under CC-BY-NC 4.0 by Meta — **check commercial-use
  terms** before shipping in a paid product; alternatives (Piper/VITS community
  voices, or your own trained model from the voice bank) avoid the NC clause.

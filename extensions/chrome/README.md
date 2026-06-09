# EYEWAZ Read Aloud — Chrome / Edge extension

Select any text on a web page and hear it in natural Urdu, spoken by your EYEWAZ
self-hosted voice service. Works in Chrome, Edge, Brave, and other Chromium
browsers (Manifest V3).

## What it does
- **Right-click → "Read with EYEWAZ (Urdu)"** on selected text.
- **Keyboard:** `Alt+Shift+U` reads the current selection, `Alt+Shift+S` stops.
- **Popup:** a Read/Stop button, a speed slider, and the voice-service URL + key.

It sends the selected text to your TTS service (`POST /tts`) and plays the
returned audio. Best for Urdu-script pages (news, books, articles). For English
pages, translate first in the EYEWAZ app — this extension speaks text as-is.

## Install (unpacked, for testing)
1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top-right).
3. Click **Load unpacked** and choose this `extensions/chrome` folder.
4. Click the EYEWAZ icon → open **Voice service settings** and set:
   - **TTS service URL** — e.g. `http://167.233.35.30:8090` (your Hetzner box).
   - **API key** — the `X-API-Key` your service expects (leave blank if none).

## Important notes
- The service URL/key live in the user's browser. If you publish this on the
  Chrome Web Store, **do not bake in a shared key** — either ship a public,
  rate-limited TTS endpoint or add per-user auth. For personal/pilot use the
  user pastes their own URL + key (as above).
- `http://` services work for local/testing. For a published extension and for
  HTTPS pages, front the TTS service with TLS (the `caddy` profile in
  `tts-service/deploy/docker-compose.yml`) and use an `https://` URL here.
- Latency = one network round-trip per selection. Great for "read this
  paragraph/article"; for instant speech use the on-device path (Android engine
  / NVDA add-on with a local model).

## Publishing
Zip the contents of this folder (not the parent) and upload at the
[Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole).
Edge uses the same package at the Microsoft Partner Center.

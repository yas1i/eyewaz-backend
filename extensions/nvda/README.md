# EYEWAZ Urdu voice — NVDA add-on

Adds **EYEWAZ Urdu** as a synthesizer in [NVDA](https://www.nvaccess.org/) (the
free, open-source Windows screen reader). Once selected, *everything* NVDA
speaks — menus, web pages, documents, any Windows app — comes out in Urdu,
spoken by your EYEWAZ self-hosted TTS service.

This is the real "Urdu screen reader" path on Windows: NVDA does the screen
reading; EYEWAZ provides the voice.

## Build
```bash
cd extensions/nvda
./build.sh            # produces eyewaz-1.0.0.nvda-addon
```
(or just zip `manifest.ini` + `synthDrivers/` + `eyewaz.json` and rename to
`.nvda-addon`.)

## Install
1. Copy `eyewaz-1.0.0.nvda-addon` to the Windows machine.
2. Double-click it (or in NVDA: **NVDA menu → Tools → Add-on store → Install
   from external source**). Confirm and restart NVDA.
3. **NVDA menu → Preferences → Settings → Speech → Synthesizer → EYEWAZ Urdu.**
4. Set Rate and Volume there like any other voice.

## Configure the voice service
Before building, edit **`eyewaz.json`**:
```json
{ "TTS_URL": "http://167.233.35.30:8090", "API_KEY": "", "TIMEOUT": 30 }
```
- `TTS_URL` — your EYEWAZ TTS service.
- `API_KEY` — the `X-API-Key` it expects (blank if none).

## How it works
The driver POSTs each chunk of NVDA's speech to `/tts`, receives a WAV, and
streams it to NVDA's audio player on a background thread (so the screen reader
never freezes). Rate maps to the service's `speed`; volume is applied locally.

## Honest limitations (MVP)
- **Latency.** Each utterance is a network round-trip, so speech starts a moment
  after you move focus — fine for reading, less snappy than a local voice for
  fast navigation. The fix is an **on-device** model: run our trained Piper voice
  locally (small local server or a future bundled build) so there's no network.
- **No per-word caret highlighting.** Index callbacks fire per chunk, not per
  character, so "say all" works but exact word-by-word tracking is approximate.
- Needs the service reachable. If it's down, NVDA falls silent for that utterance
  (check the NVDA log: **NVDA menu → Tools → View log**).

## Next step for instant, offline speech
Bundle the trained Piper `.onnx` with a tiny local synth (e.g. `sherpa-onnx` or
a localhost Piper server) and point `TTS_URL` at `http://127.0.0.1:<port>`. Then
NVDA speaks Urdu instantly, offline, with no per-character fees.
